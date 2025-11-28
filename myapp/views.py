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
from .utils import verified_user_ids
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
    
    # Fetch personalized feed
    from .algorithms import get_personalized_feed
    feed_items = get_personalized_feed(request, type=feed_type, page=1, per_page=20)
    
    logform = LogForm()
    context = {
        'logform': logform,
        'feed_items': feed_items,
        'feed_type': feed_type,
    }

    # User is authenticated and profile is complete
    return render(request, 'myapp/home.html', context)

@login_required
def load_more_feed(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    page = int(request.GET.get('page', 1))
    type = request.GET.get('feed', 'all')

    suggested_peoples = get_explore_users(filter_dev=userinfo.objects.all(), request=request, count=7, order_by='?')
    offset = (page - 1) * 10
    feed_page = get_personalized_feed(request, type=type, page=page, per_page=7)
    print(feed_page)
    html = render_to_string('myapp/feed_items.html', {'feed_items': feed_page, 'suggested_peoples': suggested_peoples, 'offset': offset}, request=request)

    return JsonResponse({
        'html': html,
        'has_next': feed_page.has_next()
    })

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
    
    #latest 5 logs 
    recent_logs = logs[:5]
    
    section = request.GET.get('section', 'overview') 
    print(section)
    
    is_following = request.user.info.is_following(userinfo_obj)
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
def follow_list(request, username):
        userinfo_obj = userinfo.objects.get(user__username = username) #user-profile list
        l = request.GET.get('list')
        grp = False
        if l == None:
            return HttpResponseRedirect(f'{request.path}?list=followers')
        if l == 'followers':
            list = userinfo_obj.get_followers()
        elif l == 'following':   
            list = userinfo_obj.get_following()
        else:
            # Invalid list type, default to followers
            return HttpResponseRedirect(f'{request.path}?list=followers')
        
        print(list)
        p = Paginator(list, 20)
        page_number = request.GET.get('page')
        page_obj = p.get_page(page_number)
        context = {
            'userinfo_obj': userinfo_obj,
            'user_list': page_obj,
            'l': l,
            'grp': grp,
        }
        
        return render(request, 'myapp/followList.html', context)

#explore page:
@login_required
def explore_dev(request):

    status_filter = request.GET.get('status', '').strip()  #ID
    skill_filter = request.GET.get('skill', '').strip()    #ID
    query = request.GET.get('q', '').strip()
    
    filter_conditions = {}
    if status_filter:
        filter_conditions["status__id"] = status_filter 
    if skill_filter:
        filter_conditions["skills__id"] = skill_filter
    
    filter_dev = userinfo.objects.filter(**filter_conditions).exclude(user=request.user).filter(user__in=verified_user_ids).select_related('user')

    if query:
        filter_dev = filter_dev.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__username__iexact=query) |
            Q(skills__name__iexact=query) |
            Q(status__name__iexact=query) |
            Q(about_user__icontains=query)
        ).distinct()
    
    applied_filter = bool(status_filter or skill_filter)
    
    if not (applied_filter or query):
        filter_dev = get_explore_users(filter_dev, request)
        
    top_skill= top_skills_list()
    status = user_status.objects.all()
    #Pagination
    p = Paginator(filter_dev, 25)
    page_number = request.GET.get('page')
    try:
        page_obj = p.page(page_number)
    except PageNotAnInteger:
        page_obj = p.page(1)
    r = filter_dev.count()
    context = {
        'filter_user': page_obj,
        'top_skill': top_skill,
        'status_list': status,   
        'total_result': r,  
        'query': query,
        'applied_filter': applied_filter,
        'active_explore_dev': True
    }
    return render(request, 'myapp/explore_dev.html', context)



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
