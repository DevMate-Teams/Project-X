from django.db import models
import uuid
from django.contrib.auth.models import User
from django.urls import reverse
from .filter import skill, user_status, CodingStyle
from phonenumber_field.modelfields import PhoneNumberField
from django.utils import timezone

class userinfo(models.Model):
    GENDER_CHOICES = [
    ('M', 'Male'),
    ('F', 'Female'),
    ('NB', 'Non-Binary'),
    ('O', 'Other'),
    ('N', 'Prefer not to say'),
]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='info')
    bio = models.TextField(blank=True, null=True)
    dob = models.DateField(null=True, blank=True)
    contact_email = models.EmailField(max_length=255, blank=True, null=True)
    about_user = models.TextField(max_length=1000, blank=True, null=True) 
    profile_image = models.ImageField(upload_to='user_profile_img', height_field=None, default='user_profile_img/profile.jpg')
    banner_image = models.CharField(max_length=255, default='banners/default.jpg', blank=True, null=True)
    location = models.CharField(max_length=200, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    # Geo-coordinates for Local feed algorithm (auto-set by system)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, db_index=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, db_index=True)
    # Separate timestamps for different geolocation methods
    location_ip_updated_at = models.DateTimeField(null=True, blank=True, help_text="When IP-based location was last updated")
    location_browser_updated_at = models.DateTimeField(null=True, blank=True, help_text="When browser GPS location was last updated")
    website = models.URLField(blank=True, null=True)
    phone = PhoneNumberField(blank=True, null=True)
    gender = models.CharField(max_length=25, null=True, blank=True, choices=GENDER_CHOICES)
    status = models.ForeignKey(user_status, related_name='developers', on_delete=models.SET_NULL, null=True, blank=True)

    github = models.URLField(blank=True, null=True)  
    linkedin = models.URLField(blank=True, null=True) 
    twitter = models.URLField(blank=True, null=True) 
    stackoverflow = models.URLField(blank=True, null=True) 
    
    skills = models.ManyToManyField(skill, related_name='users', blank=True)
    years_of_experience = models.PositiveIntegerField(blank=True, null=True)
    coding_style = models.ForeignKey(CodingStyle, on_delete=models.SET_NULL, null=True, blank=True, related_name='users')
    created_at = models.DateField(auto_now=False, auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    needs_profile_completion = models.BooleanField(default=False)
    last_seen = models.DateTimeField(default=timezone.now)
    timezone = models.CharField(max_length=63, default='UTC', help_text="User's timezone for displaying dates/times")
    
    def __str__(self):
        return self.user.username 

    def get_absolute_url(self):
        return reverse("user_info_detail", kwargs={"pk": self.pk})
    
    #following methods:from your
    def follow(self, other_user):
        if not self.is_following(other_user):
            follow.objects.create(follower = self, following=other_user)
            # Invalidate recommendation cache
            from myapp.utils.recommendations import invalidate_recommendation_cache
            invalidate_recommendation_cache(self)
    
    def unfollow(self, other_user):
        if self.is_following(other_user):
            follow.objects.filter(follower = self, following = other_user).delete()
            # Invalidate recommendation cache
            from myapp.utils.recommendations import invalidate_recommendation_cache
            invalidate_recommendation_cache(self)
    
    def is_following(self, other_user):
        return follow.objects.filter(follower = self, following = other_user).exists()
    
    def get_followers(self):
        return userinfo.objects.filter(following__following=self).order_by('-following__created_at')
    
    def get_following(self):
        return userinfo.objects.filter(followers__follower = self).order_by('-followers__created_at')

class education(models.Model):
    user = models.OneToOneField(userinfo, on_delete=models.CASCADE, related_name='education')
    name = models.CharField(max_length=100)
    degree = models.CharField(max_length=255, blank=True, null=True)
    field_of_study = models.CharField(max_length=255, null=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    till_now = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.id}-{self.user}"

    def __str__(self):
        return self.name

class experience(models.Model): 
    user = models.ForeignKey(userinfo, related_name='experiences', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    role = models.TextField(max_length=60)
    description = models.TextField(blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    till_now = models.BooleanField(default=False)
    
    def __str__(self):
        return self.name
    
class follow(models.Model):
    follower = models.ForeignKey(userinfo, related_name='following', on_delete=models.CASCADE)
    following = models.ForeignKey(userinfo, related_name='followers', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.follower.user.username} {self.following.user.username}"
    
    class Meta:
        unique_together = ('follower', 'following') 
        
