from calendar import month_name
from itertools import islice
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from .forms import LogForm, CommentForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from .models import Log, Reaction, Comment
from .utils.streaks import get_24h_log_stats, streak_calculation, calculate_max_streak
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from collections import Counter, defaultdict
from datetime import date, timedelta
from django.db.models import Avg, Q
from django.contrib import messages
from myapp.models import userinfo

def chunk_list(data, size):
    it = iter(data)
    return list(iter(lambda: list(islice(it, size)), []))

def build_contribution_months(contribution_days):
    """
    Organizes contribution days into weeks grouped by month.
    Now expects contribution_days to have date objects, not strings.
    """
    months = [[] for _ in range(12)]
    
    for day in contribution_days:
        # Extract month from date object (1-12) and convert to 0-indexed
        date_obj = day['date']
        month_index = date_obj.month - 1
        months[month_index].append(day)
    
    # Build weekly structure - include ALL months (empty or not)
    contribution_months = []
    for idx, days in enumerate(months):
        weeks = chunk_list(days, 7)
        contribution_months.append((month_name[idx+1], weeks))
    
    return contribution_months


def load_more_profile_logs(request, username):
    """
    Cursor-based pagination for loading more logs on user profile.
    Uses timestamp cursor for efficient pagination.
    """
    user = get_object_or_404(User, username=username)
    info = user.info
    
    # Get cursor (last log timestamp) from request
    cursor = request.GET.get("cursor")
    per_page = 10  # Load 10 logs at a time
    
    # Build query
    logs_query = Log.objects.filter(user=info).order_by("-timestamp")
    
    # Apply cursor filter if provided
    if cursor:
        try:
            cursor_datetime = timezone.datetime.fromisoformat(cursor)
            logs_query = logs_query.filter(timestamp__lt=cursor_datetime)
        except (ValueError, TypeError):
            pass  # Invalid cursor, just ignore it
    
    # Fetch one extra to check if there are more
    logs = list(logs_query[:per_page + 1])
    
    has_next = len(logs) > per_page
    if has_next:
        logs = logs[:per_page]  # Remove the extra one
    
    # Get new cursor (timestamp of last log)
    new_cursor = logs[-1].timestamp.isoformat() if logs else None
    
    # Render HTML
    html = render_to_string(
        "logs/partials/personal_log_cards.html",
        {"logs": logs, "user": request.user},
        request=request
    )
    
    return JsonResponse({
        "logs_html": html,
        "has_next": has_next,
        "cursor": new_cursor
    })


@require_POST
@login_required
def save_log(request):
    if request.method == "POST":
        logform = LogForm(request.POST, request.FILES)
        if logform.is_valid():
            log = logform.save(commit=False)
            log.user = request.user.info
            raw_snippet = request.POST.get('code_snippet', '').strip()
            log.code_snippet = raw_snippet[:10000] if raw_snippet else None
            log.link = request.POST.get('link', '').strip()

            log.save()
            
            from myapp.timezone_utils import user_today
            today = user_today(request.user)
            logs = Log.objects.filter(user = request.user.info)
            existing_logs_today = logs.filter(timestamp__date=today).exclude(sig=log.sig).exists() 
            
            if not existing_logs_today:
                streak = streak_calculation(logs, request.user)
                request.session['reward_message'] =  f"🔥 {streak} Day Streak!"
                request.session['reward_emojis'] = ['🥳', '🔥']
            else: 
                messages.success(request, "Log committed successfully!")
            return redirect("index")
    return redirect(request.META.get('HTTP_REFERER', '/'))

@login_required
@require_POST
def delete_log(request, sig):
    userinfo = request.user.info
    try:
        log = Log.objects.get(sig=sig)
    except Log.DoesNotExist:
        return JsonResponse({'error': 'Log not found'}, status=404)

    if log.user != userinfo:
        return JsonResponse({'error': 'Unauthorized access'}, status=403)

    log.delete()
    return JsonResponse({'success': True})

@login_required
@require_POST
def toggle_reaction(request, sig):
    """
    Toggle reaction on a log.
    If reaction exists:
        - If same emoji: remove it
        - If different emoji: update it
    If reaction doesn't exist: create it
    """
    
    log = get_object_or_404(Log, sig=sig)
    user_info = request.user.info
    emoji = request.POST.get('emoji')
    
    # Validate emoji
    valid_emojis = [choice[0] for choice in Reaction.REACTION_CHOICES]
    if emoji not in valid_emojis:
        return JsonResponse({'error': 'Invalid reaction'}, status=400)
    
    try:
        reaction = Reaction.objects.get(mindlog=log, user=user_info)
        if reaction.emoji == emoji:
            # Same reaction - remove it
            reaction.delete()
            status = 'removed'
            user_reaction = None
        else:
            # Different reaction - update it
            reaction.emoji = emoji
            reaction.save()
            status = 'updated'
            user_reaction = emoji
    except Reaction.DoesNotExist:
        # No reaction - create new one
        Reaction.objects.create(mindlog=log, user=user_info, emoji=emoji)
        status = 'added'
        user_reaction = emoji
    
    # Get updated counts
    counts = log.get_reaction_counts()
    
    return JsonResponse({
        'status': status,
        'counts': counts,
        'user_reaction': user_reaction
    })

@login_required
@require_POST
def add_comment(request, sig):
    log = get_object_or_404(Log, sig=sig)
    form = CommentForm(request.POST)
    
    if form.is_valid():
        comment = form.save(commit=False)
        comment.mindlog = log
        comment.user = request.user.info
        
        # Handle reply
        parent_id = request.POST.get('parent_id')
        actual_parent_user = None  # Track the actual user being replied to
        if parent_id:
            try:
                parent_comment = Comment.objects.get(id=parent_id)
                actual_parent_user = parent_comment.user  # Store before flattening
                
                # If replying to a reply (nested), flatten it
                if parent_comment.parent_comment:
                    # Link to the top-level parent
                    comment.parent_comment = parent_comment.parent_comment
                    # Add mention to content if not already present
                    mention = f"@{parent_comment.user.user.username}"
                    if not comment.content.strip().startswith(mention):
                        comment.content = f"{mention} {comment.content}"
                else:
                    # Direct reply to top-level comment
                    comment.parent_comment = parent_comment
                    
            except Comment.DoesNotExist:
                pass
        
        # Store actual parent user as temporary attribute for signal handler
        if actual_parent_user:
            comment._actual_parent_user = actual_parent_user
                
        comment.save()
        
        # Return JSON for AJAX
        return JsonResponse({
            'success': True,
            'comment_id': comment.id,
            'user': comment.user.user.username,
            'user_image': comment.user.profile_image.url if comment.user.profile_image else None,
            'content': comment.content,
            'timestamp': comment.timestamp.strftime('%b %d, %Y, %I:%M %p'),
            'parent_id': comment.parent_comment.id if comment.parent_comment else None,
            'can_delete': True  # User just created it, so they can delete it
        })
    
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)

@login_required
@require_POST
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    
    # Allow deletion by comment owner or log owner
    if comment.user != request.user.info and comment.mindlog.user != request.user.info:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    # Count total comments to be deleted (parent + all nested replies)
    def count_nested_comments(comment):
        count = 1  # Count the comment itself
        for reply in comment.replies.all():
            count += count_nested_comments(reply)
        return count
    
    total_deleted = count_nested_comments(comment)
    
    comment.delete()
    return JsonResponse({'success': True, 'deleted_count': total_deleted})


@login_required
@require_GET
def search_users_for_mention(request):
    """
    API endpoint for @mention autocomplete.
    Returns matching usernames as the user types.
    """
    query = request.GET.get('q', '').strip()
    
    if not query or len(query) < 1:
        return JsonResponse({'users': []})
    
    # Search users by username, prioritizing:
    # 1. Users the current user follows
    # 2. Users who have interacted with the current user
    # 3. All other matching users
    
    current_user = request.user.info
    
    # Get users matching the query
    users = User.objects.filter(
        Q(username__icontains=query) | 
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query)
    ).exclude(
        id=request.user.id  # Exclude current user
    ).select_related('info')[:15]
    
    # Get IDs of users the current user follows
    following_ids = set(
        current_user.following.values_list('following__user_id', flat=True)
    )
    
    # Build result list with priority
    result = []
    for user in users:
        try:
            info = user.info
            result.append({
                'username': user.username,
                'full_name': f"{user.first_name} {user.last_name}".strip() or user.username,
                'profile_image': info.profile_image.url if info.profile_image else '/static/assets/default-avatar.png',
                'is_following': user.id in following_ids,
            })
        except userinfo.DoesNotExist:
            continue
    
    # Sort: followed users first, then alphabetically
    result.sort(key=lambda x: (not x['is_following'], x['username'].lower()))
    
    return JsonResponse({'users': result[:10]})


@login_required
@require_POST
def track_log_view(request):
    """
    Track when a user views a log in their feed.
    Used for calculating feed freshness penalties.
    
    Expects POST data:
    - log_sig: The signature of the log being viewed
    """
    import json
    from .models import Log, LogViews
    
    try:
        data = json.loads(request.body)
        log_sig = data.get('log_sig')
        
        if not log_sig:
            return JsonResponse({'error': 'log_sig required'}, status=400)
        
        log = Log.objects.get(sig=log_sig)
        user = request.user.info
        
        # Create or update the view record
        log_view, created = LogViews.objects.get_or_create(
            user=user,
            log=log
        )
        
        if not created:
            # Increment view count for existing record
            log_view.increment_view()
        
        return JsonResponse({
            'success': True,
            'created': created,
            'view_count': log_view.view_count
        })
        
    except Log.DoesNotExist:
        return JsonResponse({'error': 'Log not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def track_batch_log_views(request):
    """
    Track multiple log views in a single request (more efficient).
    
    Expects POST data:
    - log_sigs: Array of log signatures being viewed
    """
    import json
    from .models import Log, LogViews
    from django.utils import timezone
    
    try:
        data = json.loads(request.body)
        log_sigs = data.get('log_sigs', [])
        
        if not log_sigs:
            return JsonResponse({'error': 'log_sigs required'}, status=400)
        
        user = request.user.info
        
        # Get all logs by signature
        logs = Log.objects.filter(sig__in=log_sigs)
        log_map = {log.sig: log for log in logs}
        
        # Get existing views for these logs
        existing_views = LogViews.objects.filter(
            user=user,
            log__in=logs
        ).select_related('log')
        existing_view_map = {view.log.sig: view for view in existing_views}
        
        created_count = 0
        updated_count = 0
        
        for sig in log_sigs:
            if sig not in log_map:
                continue  # Log doesn't exist
            
            if sig in existing_view_map:
                # Increment view count and update timestamp
                view = existing_view_map[sig]
                view.view_count += 1
                view.viewed_at = timezone.now()
                view.save(update_fields=['view_count', 'viewed_at'])
                updated_count += 1
            else:
                # Create new view
                LogViews.objects.create(
                    user=user,
                    log=log_map[sig]
                )
                created_count += 1
        
        return JsonResponse({
            'success': True,
            'created': created_count,
            'updated': updated_count,
            'total': created_count + updated_count
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

