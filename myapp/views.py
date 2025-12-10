from django.views.decorators.http import require_POST
import base64
from django.core.files.base import ContentFile
from django.utils import timezone
from django.utils.timezone import now, localtime
from datetime import timedelta
from django.db.models import F, Avg
from django.http import Http404, HttpResponse, HttpResponseNotAllowed, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth import login,logout,authenticate
from django.urls import reverse, reverse_lazy
from django.views import View
from .forms import RegistrationForm, EditProfileForm, EditEducationForm, EditExperienceForm, EditSkillForm, Postsignup_infoForm
from logs.forms import LogForm
from django.contrib.auth.models import User
from .models import userinfo, user_status, education, experience, CodingStyle
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, PageNotAnInteger
from django.db.models import Q
from django.template.loader import render_to_string
from itertools import groupby
from .algorithms import get_explore_users, get_personalized_feed, top_skills_list
from allauth.account.views import PasswordChangeView
from django.contrib import messages
from datetime import date, timedelta

#Logs
from logs.models import Log
from logs.views import build_contribution_months
from logs.utils.streaks import streak_calculation, calculate_max_streak

# Create your views here.
class CustomPasswordChangeView(PasswordChangeView):
    # Redirect to this URL after a successful password change
    success_url = reverse_lazy('index')

@login_required
def post_login_check(request):
    user_info = request.user.info
    if user_info.needs_profile_completion:
        return redirect('signup_about', uuid=user_info.uuid)
    return redirect('/')

#Auth:
class sign_up(View):
    def get(self, request):
        form = RegistrationForm()
        context = {
            'form': form
        }
        return render(request, 'registration/sign_up.html', context)
    
    def post(self, request):
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            userinfo.objects.create(user=user)
            education.objects.create(user = user.info)
            # SavedItem creation removed in MindLog pivot
            # user.save()
            
            username = form.cleaned_data.get("username") #Authenticate the user:
            password = form.cleaned_data.get("password1")
            email = form.cleaned_data.get("email")
            user = authenticate(username = username, password=password)
            if user is not None:
                login(request, user) # Log the user in
                print(user)
                reverse_url = reverse("signup_about", args=[user.info.uuid])
                return redirect(reverse_url)
        context = {
            'form': form
        }
        return render(request, 'registration/sign_up.html', context)
        
@login_required
def signup_about(request, uuid):
    if request.method == 'POST':
        userinfo_obj = request.user.info
        bio_input = request.POST.get('bio', '')
        userinfo_obj.bio = bio_input.replace('\n', ' ').replace('\r', '').strip()
        userinfo_obj.linkedin =request.POST.get('linkedin')
        userinfo_obj.website = request.POST.get('website')
        userinfo_obj.stackoverflow = request.POST.get('stackoverflow')
        userinfo_obj.github = request.POST.get('github')
        userinfo_obj.save()
        reverse_url = reverse("signup_character", args=[userinfo_obj.uuid])
        return redirect(reverse_url)
    context = {}
    return render(request, 'myapp/signup-about.html', context)

@login_required
def signup_character(request, uuid):
    form = Postsignup_infoForm(instance=request.user.info)
    if request.method == 'POST':
        form = Postsignup_infoForm(request.POST, instance=request.user.info)
        if form.is_valid():
            form.save()
            reverse_url = reverse("signup_skills", args=[request.user.info.uuid])
            return redirect(reverse_url)
    context = {
        'form': form
    }
    return render(request, 'myapp/signup-character.html', context)

@login_required
def signup_skills(request, uuid):
    skill_form = EditSkillForm(instance=request.user.info)
    if request.method == 'POST':
        skill_form = EditSkillForm(request.POST, instance=request.user.info)
        if skill_form.is_valid():
            request.user.info.needs_profile_completion = False
            request.user.info.save()
            skill_form.save()
            return redirect('/')
    context = {
        'form': skill_form
    }
    return render(request, 'myapp/signup-selectskill.html', context)

def contribute_page(request):
    return render(request, 'myapp/contribute.html')

def feedback_page(request):
    return render(request, 'myapp/feedback.html')

def home_page(request):
    if not request.user.is_authenticated:
        return render(request, 'myapp/landing_page.html')
    
    if request.user.info.needs_profile_completion:
        return redirect('signup_about', uuid=request.user.info.uuid)
    
    # Get feed type from query params
    feed_type = request.GET.get('feed', 'network')
    
    # Fetch personalized feed (cursor-based pagination)
    from .algorithms import get_personalized_feed
    feed_result = get_personalized_feed(request, type=feed_type, per_page=20, cursor=None)
    feed_items = feed_result['items']
    next_cursor = feed_result['next_cursor']
    has_next = feed_result['has_next']
    
    # Fetch trending logs (What's Hot Now) - Only for Global tab
    trending_logs = []
    if feed_type == 'global':
        from logs.utils.trending import get_trending_logs
        trending_logs = get_trending_logs(limit=5, hours=24)
    
    logform = LogForm()
    
    # Get popular developers for empty feed state (Network tab only)
    popular_developers = []
    if feed_type == 'network' and len(feed_items) == 0:
        from .utils.popular_developers import get_popular_developers
        popular_developers = get_popular_developers(request.user, limit=10)
    
    # Get nearby developers for Local tab
    nearby_developers = []
    if feed_type == 'local':
        from .utils.nearby_developers import get_nearby_developers
        nearby_developers = get_nearby_developers(request.user, limit=7)
    
    context = {
        'logform': logform,
        'feed_items': feed_items,
        'feed_type': feed_type,
        'trending_logs': trending_logs,
        'populate_popular_developers': popular_developers,
        'nearby_developers': nearby_developers,
        'next_cursor': next_cursor,
        'has_next': has_next,
    }

    # User is authenticated and profile is complete
    return render(request, 'myapp/home.html', context)

@login_required
def load_more_feed(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    cursor = request.GET.get('cursor', None)
    type = request.GET.get('feed', 'all')

    suggested_peoples = get_explore_users(filter_dev=userinfo.objects.all(), request=request, count=7, order_by='?')
    
    # Use cursor-based pagination
    feed_result = get_personalized_feed(request, type=type, per_page=7, cursor=cursor)
    
    html = render_to_string('myapp/feed_items.html', {
        'feed_items': feed_result['items'], 
        'suggested_peoples': suggested_peoples
    }, request=request)

    return JsonResponse({
        'html': html,
        'has_next': feed_result['has_next'],
        'next_cursor': feed_result['next_cursor']
    })

@login_required
def view_log_in_feed(request, log_sig):
    """
    Display a specific log in the home feed with highlighting
    Routes from notifications and trending logs to show the target log in feed context
    """
    from logs.models import Log
    from logs.utils.trending import get_trending_logs
    
    # Get the target log
    try:
        target_log = Log.objects.select_related('user__user').get(sig=log_sig)
    except Log.DoesNotExist:
        # Fallback to regular home page if log doesn't exist
        return redirect('index')
    
    # Get feed type and source from query params
    feed_type = request.GET.get('feed', 'network')
    source = request.GET.get('from', 'notification')  # 'notification' or 'trending'
    
    # Fetch personalized feed (cursor-based pagination)
    from .algorithms import get_personalized_feed
    feed_result = get_personalized_feed(request, type=feed_type, per_page=20, cursor=None)
    feed_items = feed_result['items']
    
    # Check if target log is in feed, if not prepend it
    log_in_feed = any(item.id == target_log.id for item in feed_items)
    if not log_in_feed:
        # Prepend target log and limit to 20 total items
        feed_items = [target_log] + list(feed_items)[:19]
    
    # Fetch trending logs
    trending_logs = get_trending_logs(limit=5, hours=24)
    
    logform = LogForm()
    context = {
        'logform': logform,
        'feed_items': feed_items,
        'feed_type': feed_type,
        'trending_logs': trending_logs,
        'highlighted_log_sig': log_sig,  # Pass to template for highlighting
        'source': source,  # 'notification' or 'trending'
        'active_home': True,
        'next_cursor': feed_result.get('next_cursor'),
        'has_next': feed_result.get('has_next', False),
    }
    
    return render(request, 'myapp/home.html', context)

#profile-page
@login_required
def user_profile(request, user_name):
    userinfo_obj = get_object_or_404(userinfo, user__username = user_name)
    link_available = open_exp_flag = open_edu_flag = open_editprofile_flag =editprofile_form = edu_form = exp_form = skill_form  = False
    social_links = { 
    'github': userinfo_obj.github if userinfo_obj.github else None,
    'linkedin': userinfo_obj.linkedin if userinfo_obj.linkedin else None,
    'stack-overflow': userinfo_obj.stackoverflow if userinfo_obj.stackoverflow else None,
    'website': userinfo_obj.website if userinfo_obj.website else None
}
    if social_links.get('github') or social_links.get('linkedin') or social_links.get('stackoverflow') or social_links.get('website'):
        link_available = True
    skill_list = userinfo_obj.skills.all()
    exp_obj = userinfo_obj.experiences.all().order_by('-start_date')
    
    #streak and other logs calculations
    logs = Log.objects.filter(user = userinfo_obj).order_by("-timestamp")
    
    # Paginate recent logs (first 10 for initial load)
    logs_paginator = Paginator(logs, 10)
    recent_logs_page = logs_paginator.page(1)
    recent_logs = list(recent_logs_page.object_list)
    has_more_logs = recent_logs_page.has_next()
    
    # Get cursor for pagination (last log's timestamp)
    initial_cursor = recent_logs[-1].timestamp.isoformat() if recent_logs else None
    
    total_logs = logs.count()
    last_log_date = timezone.localtime(logs.first().timestamp).date() if total_logs else None
    
    
    streak_count = streak_calculation(logs, userinfo_obj.user)
    max_streak_count = calculate_max_streak(logs)
    
    year = int(request.GET.get('year', timezone.now().year))
    
    # Get user's timezone for accurate date conversion
    from myapp.timezone_utils import get_user_timezone
    import pytz
    user_tz = get_user_timezone(userinfo_obj.user)
    
    # Optimized: Use database aggregation with timezone conversion
    from django.db.models.functions import TruncDate
    from django.db.models import Count
    
    # Aggregate logs by date at database level, converting to user's timezone
    log_heat_map = logs.filter(
        timestamp__year=year
    ).annotate(
        log_date=TruncDate('timestamp', tzinfo=user_tz)
    ).values('log_date').annotate(
        count=Count('id')
    ).order_by('log_date')
    
    # Build efficient lookup dict
    log_map = {item['log_date'].strftime('%Y-%m-%d'): item['count'] 
               for item in log_heat_map}

    # Prepare full 1-year grid
    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)
    total_days = (end_date - start_date).days + 1

    contribution_days = []
    for i in range(total_days):
        current_day = start_date + timedelta(days=i)
        contribution_days.append({
            'date': current_day,  # Pass date object, not string
            'date_str': current_day.strftime('%Y-%m-%d'),  # Keep string for lookup
            'count': log_map.get(current_day.strftime('%Y-%m-%d'), 0)
        })
        
    contribution_months = build_contribution_months(contribution_days)
    log_year_count =  sum(log_map.values())
    years_available = logs.dates('timestamp', 'year')
    
    section = request.GET.get('section', 'overview') 
    print(section)
    
    is_following = request.user.info.is_following(userinfo_obj)
    
    # Calculate mutual count efficiently (only for authenticated users viewing other profiles)
    if request.user.is_authenticated and request.user != userinfo_obj.user:
        my_following_ids = request.user.info.get_following().values_list('id', flat=True)
        mutuals_queryset = userinfo_obj.get_following().filter(id__in=my_following_ids)
        mutuals_count = mutuals_queryset.count()
        # Fetch first 3 mutual connections for preview display (Instagram/LinkedIn style)
        mutuals_preview = list(mutuals_queryset[:3])
    else:
        mutuals_count = 0
        mutuals_preview = []
    
    if request.user.info == userinfo_obj: #Edit options
        edu_form = EditEducationForm(instance=request.user.info.education)
        exp_form = EditExperienceForm()
        editprofile_form = EditProfileForm(instance=request.user.info)
        skill_form = EditSkillForm(instance=request.user.info)
        
    if request.method == 'POST' and userinfo_obj == request.user.info:
        form_type = request.POST.get('form_type')
        if form_type == 'experience':
            exp_form = EditExperienceForm(request.POST)
            if exp_form.is_valid():
                form = exp_form.save(commit=False)
                form.user = request.user.info
                form.save()
                exp_form = EditExperienceForm()
            else:
                open_exp_flag = True
        elif form_type == 'education':
            action = request.POST.get('action')
            if action == 'save':
                edu_form = EditEducationForm(request.POST, instance=request.user.info.education)
                if edu_form.is_valid():
                    edu_form.save()
                else:
                    open_edu_flag = True
                    print("Form errors:", edu_form.errors)
            elif action == 'delete':
                request.user.info.education.delete()
                education.objects.create(user = request.user.info)
                redirect_url = reverse("user_profile", args=[request.user.username])
                return redirect(f"{redirect_url}?section=info")
                
        elif form_type == 'editprofile':
            editprofile_form = EditProfileForm(request.POST, request.FILES, instance = request.user.info)
            if editprofile_form.is_valid():
                userinfo_obj = editprofile_form.save(commit=False)
                
                # Extract and save location data
                city = request.POST.get('city')
                state = request.POST.get('state')
                country = request.POST.get('country')
                
                if city: userinfo_obj.city = city
                if state: userinfo_obj.state = state
                if country: userinfo_obj.country = country
                
                cropped_image_data = request.POST.get('croppedImage', '')
                if cropped_image_data:
                    try:
                        format, imgstr = cropped_image_data.split(';base64,')
                        ext = format.split('/')[-1]
                        image_data = base64.b64decode(imgstr)
                        file_name = f"{request.user.username}_profile.{ext}"
                        userinfo_obj.profile_image = ContentFile(image_data, name=file_name)
                    except (ValueError, base64.binascii.Error):
                        editprofile_form.add_error(None, "Invalid image data. Please upload a valid image.")
                        open_editprofile_flag = True
                userinfo_obj.save()
                redirect_url = reverse("user_profile", args=[request.user.username])
                return redirect(redirect_url)
            else:
                open_editprofile_flag = True
        elif form_type == 'skill':
            skill_form = EditSkillForm(request.POST, instance=request.user.info)
            if skill_form.is_valid():
                skill_form.save()
                redirect_url = reverse('user_profile', args=[request.user.username])
                return redirect(f'{redirect_url}?section=info')  
                
    context = {
        'userinfo_obj': userinfo_obj,
        'social_links': social_links,
        'link_available': link_available,
        'exp_obj': exp_obj,
        'section': section,
        'is_following': is_following,
        'mutuals_count': mutuals_count,
        'mutuals_preview': mutuals_preview,
        'ep_form': editprofile_form,
        'edu_form': edu_form,
        'exp_form': exp_form,
        'skill_form': skill_form,
        'skill_list': skill_list,
        'profile_type': 'user',
        'flag': {'open_edu_flag': open_edu_flag, 'open_exp_flag': open_exp_flag, 'open_editprofile_flag': open_editprofile_flag},

        'streak_count': streak_count,
        'max_streak_count': max_streak_count,
        'log_map': dict(log_map),
        'year': year,
        'years_available': years_available,
        'contribution_months': contribution_months,
        'log_year_count': log_year_count,
        'total_logs': total_logs,
        'last_log_date': last_log_date,
        'recent_logs': recent_logs,
        'has_more_logs': has_more_logs,
        'initial_cursor': initial_cursor,
    }
    return render(request, 'myapp/user_profile_v2.html', context)

#follow request:
@login_required
def unfollow_user(request, otheruserinfo_id):
    otheruser = userinfo.objects.get(id = otheruserinfo_id)
    user = request.user.info
    if user != otheruser:
        user.unfollow(otheruser)
        return JsonResponse({"status": "unfollowed", "message": "User unfollowed Successfully.", 'followers_count': otheruser.get_followers().count(), 'following_count': otheruser.get_following().count()})
    return JsonResponse({"status":"error", "message": "Invalid request."}, status = 400)

@login_required
def follow_user(request, otheruserinfo_id):
    otheruser = userinfo.objects.get(id = otheruserinfo_id)
    user = request.user.info
    if user != otheruser:
        user.follow(otheruser)
        return JsonResponse({"status": "followed", "message": "User followed successfully.", 'followers_count': otheruser.get_followers().count(), 'following_count': otheruser.get_following().count()})
    return JsonResponse({"status": "error", "message": "Invalid request."}, status=400)

@login_required
@require_POST
def quick_follow_user(request):
    """
    AJAX endpoint for quick follow/unfollow toggle from feed.
    Accepts username in POST data.
    Returns current follow status after toggle.
    """
    import json
    
    try:
        data = json.loads(request.body)
        target_username = data.get('username')
        
        if not target_username:
            return JsonResponse({"status": "error", "message": "Username required."}, status=400)
        
        # Get target user
        try:
            target_user = userinfo.objects.select_related('user').get(user__username=target_username)
        except userinfo.DoesNotExist:
            return JsonResponse({"status": "error", "message": "User not found."}, status=404)
        
        current_user = request.user.info
        
        # Prevent self-follow
        if current_user == target_user:
            return JsonResponse({"status": "error", "message": "Cannot follow yourself."}, status=400)
        
        # Check current follow status and toggle
        is_following = current_user.is_following(target_user)
        
        if is_following:
            # Unfollow
            current_user.unfollow(target_user)
            return JsonResponse({
                "status": "success",
                "action": "unfollowed",
                "is_following": False,
                "message": f"You unfollowed @{target_username}",
                "username": target_username
            })
        else:
            # Follow
            current_user.follow(target_user)
            return JsonResponse({
                "status": "success",
                "action": "followed",
                "is_following": True,
                "message": f"You are now following @{target_username}",
                "username": target_username
            })
        
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON data."}, status=400)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
    
@login_required
def follow_list(request, username):
        userinfo_obj = userinfo.objects.get(user__username = username) #user-profile list
        l = request.GET.get('list')
        grp = False
        if l == None:
            return HttpResponseRedirect(f'{request.path}?list=followers')
        
        # Pre-calculate following IDs for mutuals check (lazy queryset)
        # Using 'id' (userinfo PK) is cleaner than 'user__id'
        is_self = request.user == userinfo_obj.user
        my_following_ids = []
        if not is_self:
            my_following_ids = request.user.info.get_following().values_list('id', flat=True)

        if l == 'followers':
            list = userinfo_obj.get_followers()
        elif l == 'following':   
            list = userinfo_obj.get_following()
        elif l == 'mutuals':
            if is_self:
                list = userinfo.objects.none()
            else:
                # Get users that userinfo_obj follows AND are in my_following_ids
                list = userinfo_obj.get_following().filter(id__in=my_following_ids)
        else:
            # Invalid list type, default to followers
            return HttpResponseRedirect(f'{request.path}?list=followers')
        
        print(list)
        p = Paginator(list, 25)
        page_number = request.GET.get('page')
        page_obj = p.get_page(page_number)
        
        # Calculate counts for context
        followers_count = userinfo_obj.get_followers().count()
        following_count = userinfo_obj.get_following().count()
        
        if is_self:
            mutuals_count = 0
        else:
            mutuals_count = userinfo_obj.get_following().filter(id__in=my_following_ids).count()

        context = {
            'userinfo_obj': userinfo_obj,
            'user_list': page_obj,
            'l': l,
            'grp': grp,
            'followers_count': followers_count,
            'following_count': following_count,
            'mutuals_count': mutuals_count,
            'is_self': is_self,
        }
        
        return render(request, 'myapp/followList.html', context)

#explore page:
@login_required
def explore_dev(request):
    from .utils.recommendations import get_recommended_developers
    
    # Get personalized recommendations
    recommendations = get_recommended_developers(
        user=request.user,
        limit=12,
        exclude_following=True,
        use_cache=True
    )
    
    context = {
        'recommendations': recommendations,
    }
    
    return render(request, 'myapp/explore_dev.html', context)


@login_required
def load_more_recommendations(request):
    """
    API endpoint for loading more developer recommendations
    """
    from .utils.recommendations import get_recommended_developers
    from django.http import JsonResponse
    
    offset = int(request.GET.get('offset', 0))
    limit = int(request.GET.get('limit', 12))
    
    try:
        # Get recommendations with offset
        recommendations = get_recommended_developers(
            user=request.user,
            limit=limit,
            offset=offset,
            exclude_following=True,
            use_cache=True
        )
        
        # Check if there are more results
        has_more = len(recommendations) == limit
        
        # Format response
        data = []
        for dev, score, reason in recommendations:
            data.append({
                'id': dev.id,
                'username': dev.user.username,
                'avatar': dev.profile_image.url if dev.profile_image else None,
                'city': dev.city,
                'state': dev.state,
                'coding_style': {
                    'name': dev.coding_style.name,
                    'logo': dev.coding_style.logo
                } if dev.coding_style else None,
                'reason': reason,
                'score': round(score, 2),
                'is_following': request.user.info.is_following(dev)
            })
        
        return JsonResponse({
            'results': data,
            'count': len(data),
            'has_more': has_more,
            'next_offset': offset + len(data)
        })
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Load more recommendations error: {str(e)}')
        
        return JsonResponse({
            'results': [],
            'count': 0,
            'has_more': False,
            'error': 'An error occurred'
        }, status=500)



@login_required
def search_developers_api(request):
    """
    API endpoint for developer search with fuzzy matching and network ranking
    """
    from .utils.search import search_developers
    from django.http import JsonResponse
    
    query = request.GET.get('q', '').strip()
    
    # Edge case: Empty query
    if not query:
        return JsonResponse({
            'results': [],
            'count': 0,
            'message': 'Please enter a search term'
        })
    
    # Edge case: Query too short
    if len(query) < 2:
        return JsonResponse({
            'results': [],
            'count': 0,
            'message': 'Enter at least 2 characters'
        })
    
    try:
        # Perform search
        results = search_developers(query, request.user, limit=30)
        
        # Edge case: No results
        if not results:
            return JsonResponse({
                'results': [],
                'count': 0,
                'message': 'No developers found. Try different keywords.'
            })
        
        # Format response
        data = []
        for dev, score, mutual_count in results:
            data.append({
                'id': dev.id,
                'username': dev.user.username,
                'first_name': dev.user.first_name,
                'last_name': dev.user.last_name,
                'full_name': dev.user.get_full_name() or dev.user.username,
                'avatar': dev.profile_image.url if dev.profile_image else None,
                'bio': dev.bio[:150] if dev.bio else '',
                'location': dev.location or f"{dev.city}, {dev.state}" if dev.city and dev.state else dev.city or dev.state or '',
                'city': dev.city,
                'coding_style': {
                    'name': dev.coding_style.name,
                    'logo': dev.coding_style.logo
                } if dev.coding_style else None,
                'mutual_count': mutual_count,
                'score': round(score, 2),
                'is_following': request.user.info.is_following(dev)
            })
        
        return JsonResponse({
            'results': data,
            'count': len(data),
            'message': None
        })
        
    except Exception as e:
        # Log error and return graceful response
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Search error: {str(e)}')
        
        return JsonResponse({
            'results': [],
            'count': 0,
            'message': 'An error occurred. Please try again.'
        }, status=500)



@login_required
def settings_page(request):
    userinfo_obj = request.user.info
    
    # Handle timezone update
    if request.method == 'POST' and 'timezone' in request.POST:
        new_timezone = request.POST.get('timezone')
        # Validate timezone
        import pytz
        from django.contrib import messages
        from django.shortcuts import redirect
        if new_timezone in pytz.all_timezones:
            userinfo_obj.timezone = new_timezone
            userinfo_obj.save()
            messages.success(request, 'Timezone updated successfully!')
        else:
            messages.error(request, 'Invalid timezone selected.')
        return redirect('settings_page')
    
    # Get timezone choices for the dropdown
    from myapp.timezone_utils import get_common_timezones
    timezone_choices = get_common_timezones()
    
    context = {
        'userinfo_obj': userinfo_obj,
        'timezone_choices': timezone_choices,
    }
    return render(request, 'myapp/account_setting.html', context)


@login_required
@login_required
def delete_data(request):
    if request.method == "POST":
        form_type = request.POST.get("form_type")
        
        if form_type == 'delete_exp_obj':
            Id = request.POST.get("exp_id")
            print(Id)
            experience.objects.get(id = Id).delete()
            redirect_url = reverse("user_profile", args=[request.user.username])
            return redirect(f"{redirect_url}?section=info")
    return JsonResponse({"success": False, "error": "Invalid request"})

@login_required
def delete_account(request, uuid):
    print(True)
    user = request.user
    if uuid == user.info.uuid:
        user.delete()
        logout(request)
    return redirect('/')

@login_required
def logout_view(request):
    logout(request)
    list(messages.get_messages(request))  # Force-clear any leftover messages
    return redirect('account_login')

@login_required
@require_POST
def update_banner(request):
    banner_name = request.POST.get('banner')
    allowed_banners = [
        'nature.png', 'technology.png', 'science.png', 'geometry.png',
        'minimalism.png', 'space.png', 'gradients.png', 'abstract.png'
    ]
    
    if banner_name in allowed_banners:
        request.user.info.banner_image = f'banners/{banner_name}'
        request.user.info.save()
        return JsonResponse({'success': True, 'banner_url': request.user.info.banner_image})
    
    return JsonResponse({'success': False, 'error': 'Invalid banner selection'})

@login_required
@require_POST  
def update_coding_style(request):
    """Update user's coding style via AJAX"""
    
    style_id = request.POST.get('style_id')
    
    if not style_id:
        return JsonResponse({'success': False, 'error': 'No style selected'})
    
    try:
        coding_style = CodingStyle.objects.get(id=style_id)
        request.user.info.coding_style = coding_style
        request.user.info.save()
        
        return JsonResponse({
            'success': True,
            'style': {
                'id': coding_style.id,
                'name': coding_style.name,
                'logo': coding_style.logo,
                'description': coding_style.description
            }
        })
    except CodingStyle.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Invalid coding style'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def get_coding_styles(request):
    """Get all available coding styles for the modal"""
    
    styles = CodingStyle.objects.all().values('id', 'name', 'logo', 'description')
    current_style_id = request.user.info.coding_style.id if request.user.info.coding_style else None
    
    return JsonResponse({
        'styles': list(styles),
        'current_style_id': current_style_id
    })

# ============= NOTIFICATION VIEWS =============

@login_required
def notification_page(request):
    """
    Display notifications page with grouped notifications and pagination
    """
    from logs.utils.notifications import get_user_notifications, get_notification_count, group_notifications_by_date
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    
    # Get all notifications for the user (without limit for pagination)
    all_notifications = get_user_notifications(request.user)
    
    # Paginate notifications (20 per page)
    paginator = Paginator(all_notifications, 20)
    page = request.GET.get('page', 1)
    
    try:
        notifications = paginator.page(page)
    except PageNotAnInteger:
        notifications = paginator.page(1)
    except EmptyPage:
        notifications = paginator.page(paginator.num_pages)
    
    # Group by date
    grouped_notifications = group_notifications_by_date(notifications)
    
    # Get unread count
    notification_count = get_notification_count(request.user, unread_only=True)
    
    context = {
        'grouped_notifications': grouped_notifications,
        'notification_count': notification_count,
        'active_notifications': True,
        'page_obj': notifications,
        'paginator': paginator,
    }
    
    return render(request, 'myapp/notification.html', context)


@login_required
@require_POST
def mark_all_read(request):
    """
    AJAX endpoint to mark all notifications as read
    """
    from logs.utils.notifications import mark_all_as_read
    
    count = mark_all_as_read(request.user)
    
    return JsonResponse({
        'success': True,
        'marked_count': count
    })


@login_required
def get_notification_count_api(request):
    """
    AJAX endpoint to get real-time notification count for badge
    """
    from logs.utils.notifications import get_notification_count
    
    count = get_notification_count(request.user, unread_only=True)
    
    return JsonResponse({
        'count': count
    })


@login_required
@require_POST
def mark_notification_read(request, notification_id):
    """
    Mark a single notification as read
    """
    from logs.models import Notification
    
    try:
        notification = Notification.objects.get(
            id=notification_id,
            recipient=request.user.info
        )
        notification.mark_as_read()
        
        return JsonResponse({
            'success': True
        })
    except Notification.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Notification not found'
        }, status=404)


@login_required
def load_more_notifications(request):
    """
    AJAX endpoint to load more notifications for pagination
    """
    from logs.utils.notifications import get_user_notifications, group_notifications_by_date
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    from django.template.loader import render_to_string
    
    page = request.GET.get('page', 2)
    
    # Get all notifications
    all_notifications = get_user_notifications(request.user)
    
    # Paginate
    paginator = Paginator(all_notifications, 20)
    
    try:
        notifications = paginator.page(page)
    except PageNotAnInteger:
        return JsonResponse({'error': 'Invalid page number'}, status=400)
    except EmptyPage:
        return JsonResponse({
            'html': '',
            'has_more': False,
            'next_page': None
        })
    
    # Group by date
    grouped_notifications = group_notifications_by_date(notifications)
    
    # Render HTML for notifications
    html = render_to_string('notifications/notification_list_partial.html', {
        'grouped_notifications': grouped_notifications,
    }, request=request)
    
    return JsonResponse({
        'html': html,
        'has_more': notifications.has_next(),
        'next_page': notifications.next_page_number() if notifications.has_next() else None,
        'current_page': notifications.number
    })

# ============= GEOLOCATION VIEWS (Browser-Only) =============

@login_required
@require_POST
def update_user_geolocation(request):
    """
    Update user's location from browser geolocation.
    
    Expected POST data:
    - latitude: float
    - longitude: float
    """
    import json
    from .utils.geolocation import update_location
    
    try:
        data = json.loads(request.body)
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        
        if latitude is None or longitude is None:
            return JsonResponse({
                'success': False,
                'error': 'Missing latitude or longitude'
            }, status=400)
        
        # Validate coordinates
        try:
            lat = float(latitude)
            lon = float(longitude)
            
            if not (-90 <= lat <= 90):
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid latitude (must be -90 to 90)'
                }, status=400)
            
            if not (-180 <= lon <= 180):
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid longitude (must be -180 to 180)'
                }, status=400)
                
        except (ValueError, TypeError):
            return JsonResponse({
                'success': False,
                'error': 'Invalid coordinate format'
            }, status=400)
        
        success = update_location(request.user.info, lat, lon)
        
        if success:
            return JsonResponse({
                'success': True,
                'message': 'Location updated successfully'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to update location'
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def get_user_geolocation_status(request):
    """
    Get current user's geolocation status.
    Returns status and recommended action for frontend.
    """
    from .utils.geolocation import get_geolocation_status
    
    user_info = request.user.info
    status = get_geolocation_status(user_info)
    
    return JsonResponse(status)


@login_required
@require_POST
def set_permission_denied(request):
    """
    Record that user denied browser geolocation permission.
    """
    from .utils.geolocation import set_permission_denied as record_denial
    
    try:
        record_denial(request.user.info)
        return JsonResponse({
            'success': True,
            'message': 'Permission denial recorded'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

