from datetime import datetime
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
import re
from .models import userinfo, skill, education, experience
from django.forms.widgets import ClearableFileInput
# from django_select2.forms import Select2MultipleWidget
from allauth.account.forms import SignupForm, LoginForm
from django.contrib.auth import authenticate, get_user_model

User = get_user_model()

class CustomSignupForm(SignupForm):
    first_name = forms.CharField(max_length=30, label="First Name", required=True)
    last_name = forms.CharField(max_length=30, label="Last Name", required=False)

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if username:
            if len(username) > 24:
                raise forms.ValidationError("Username cannot exceed 24 characters.")
            
            is_valid = (
                username[0].isalpha() and
                bool(re.match(r'^[a-zA-Z0-9_.]+$', username)) and
                username.count('.') <= 1 and
                '..' not in username
            )
            if not is_valid:
                raise forms.ValidationError(
                    "Username must start with a letter and contain only letters, numbers, underscores, and at most one dot."
                )
                
            if not any(char.isalpha() for char in username):
                raise forms.ValidationError("Username must contain at least one letter and cannot be entirely numeric.")
            
            if not username.islower():
                raise forms.ValidationError("Username must not contain uppercase letters.")
        
            if User.objects.filter(username=username).exists():
                raise forms.ValidationError("A user with this username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if not email:
            raise forms.ValidationError("Email should not be empty.")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email already exists.")
        return email

    def save(self, request):
        user = super().save(request)
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.save()
        return user

class CustomClearableFileInput(ClearableFileInput):
    clear_checkbox_label = ''
    initial_text = ''
    input_text = 'Change'
    template_name = 'widgets/custom_file_input.html'  # Optional for more customization

class RegistrationForm(UserCreationForm):
    class Meta:
        model = User
        fields =  ["first_name", "last_name", "username", "email", "password1", "password2"]
    
        help_texts = {
            'username': "Enter Unique Username"
        }
    def clean_username(self):
        username = self.cleaned_data.get("username")
        is_valid = username[0].isalpha() and bool(re.match(r'^[a-zA-Z0-9_.]+$', username)) and username.count('.') <= 1  and '..' not in username
        if is_valid==False:
            raise forms.ValidationError("Username must start with a letter and contain only letters, numbers, underscore and dot")
        return username
    
    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email == None or email == "":
            raise forms.ValidationError("Email Should not be Empty")
        elif User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email already Exists.")
        return email
    
class Postsignup_infoForm(forms.ModelForm):
    class Meta:
        model = userinfo
        fields = ['status', 'coding_style', 'timezone']
        widgets = {
            'coding_style': forms.Select(attrs={
                'class': 'w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent'
            }),
            'status': forms.Select(attrs={
                'class': 'w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent'
            }),
            'timezone': forms.Select(attrs={
                'class': 'w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent',
                'style': 'height: 48px; max-height: 48px;',
                'size': '1'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate timezone choices
        from myapp.timezone_utils import get_common_timezones
        self.fields['timezone'].widget.choices = get_common_timezones()
        self.fields['timezone'].required = True

class EditProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={'class': 'outline-none border-gray-700 bg-[#262b34] text-[#ffffff] px-2 py-1', 'placeholder': 'First'}))
    last_name = forms.CharField(max_length=50, required=False, widget=forms.TextInput(attrs={'class': 'outline-none border-gray-700 bg-[#262b34] text-[#ffffff] px-2 py-1', 'placeholder': 'Last'}))
    username = forms.CharField(max_length = 24, required=True, widget=forms.TextInput(attrs={'class': 'outline-none border-gray-700 bg-[#262b34] text-[#ffffff] px-2 py-1', 'placeholder': 'Username'}))
    
    class Meta:
        model = userinfo
        exclude = ['user', 'years_of_experience', 'skills', 'profile_views', 'updated_at', 'needs_profile_completion', 'last_seen', 'timezone', 'coding_style']
        
        widgets = {
            'bio': forms.Textarea(attrs={'class': 'outline-none border border-gray-700 bg-[#262b34] text-[#ffffff] px-2 py-2', 'placeholder': 'Bio...', 'rows': 7,'cols': 40,}),
            'dob': forms.DateInput(attrs={'type': 'date', 'class': 'outline-none border-gray-700 bg-[#262b34] text-[#ffffff] px-2 py-2', 'id':"dob"}),
            'location': forms.TextInput(attrs={'class': 'outline-none border-gray-700 bg-[#262b34] text-[#ffffff] px-2 py-2', 'placeholder': 'Location'}),
            'contact_email': forms.EmailInput(attrs={'class': 'outline-none border-gray-700 bg-[#262b34] text-[#ffffff] px-2 py-2', 'placeholder': 'Email'}),
            'phone': forms.TextInput(attrs={'type': 'tel','class': 'outline-none border-gray-700 bg-[#262b34] text-[#ffffff] px-2 py-2', 'placeholder': 'Phone'}),
            'gender': forms.Select(attrs={'class': 'outline-none border-gray-700 bg-[#262b34] text-[#ffffff] px-2 py-2', }),
            'status': forms.Select(attrs={'class': 'outline-none border-gray-700 bg-[#262b34] text-[#ffffff] px-2 py-2', }),
            'website': forms.URLInput(attrs={'class': 'outline-none border-gray-700 bg-[#262b34] text-[#ffffff] px-2 py-2', 'placeholder': 'www.samplesite.in'}),
            'linkedin': forms.URLInput(attrs={'class': 'outline-none border-gray-700 bg-[#262b34] text-[#ffffff] px-2 py-2', 'placeholder': 'Linkedin URL'}),
            'github': forms.URLInput(attrs={'class': 'outline-none border-gray-700 bg-[#262b34] text-[#ffffff] px-2 py-2', 'placeholder': 'Github URL'}),
            'stackoverflow': forms.URLInput(attrs={'class': 'outline-none border-gray-700 bg-[#262b34] text-[#ffffff] px-2 py-2', 'placeholder': 'Stackoverflow URL'}),
            'profile_image': forms.ClearableFileInput(attrs={'id': 'imgInput','class': 'hidden'}),
        }
        labels = {
            'bio': 'Short Bio',
            'contact_email': 'Contact Email (If any)',
        }
        
    def __init__(self, *args, **kwargs):
        super(EditProfileForm, self).__init__(*args, **kwargs)
        
        if self.instance and self.instance.user:
            user = self.instance.user
            self.fields['first_name'].initial =  user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['username'].initial = user.username
            
    def clean_username(self):
        """
        Validates the username field to ensure it:
          - Starts with a letter.
          - Contains only letters, numbers, underscore, and dot.
          - Has at most one dot.
          - Does not contain consecutive dots.
        """
        username = self.cleaned_data.get("username")
        if username:
            is_valid = (
                username[0].isalpha() and
                bool(re.match(r'^[a-zA-Z0-9_.]+$', username)) and
                username.count('.') <= 1 and
                '..' not in username
            )
            if not is_valid:
                raise forms.ValidationError(
                    "Username must start with a letter and contain only letters, numbers, underscores, and a single dot (with no consecutive dots)."
                )
            if not any(char.isalpha() for char in username):
                raise forms.ValidationError("Username must contain at least one letter and cannot be entirely numeric.")
            
            if not username.islower():
                raise forms.ValidationError("Username must not contain uppercase letters.")

            qs = User.objects.filter(username=username)
            if self.instance.user:
                qs = qs.exclude(pk=self.instance.user.pk)
            if qs.exists():
                raise forms.ValidationError("This username is already taken.")
        return username
            
    def save(self,commit=True):
        user = self.instance.user
        user.first_name = self.cleaned_data.get('first_name')
        user.last_name = self.cleaned_data.get('last_name')
        user.username = self.cleaned_data.get('username')
        
        user.full_clean()
        user.save()
        instance = super(EditProfileForm, self).save(commit=False)
        if commit:
            instance.save()
        return instance
    
class EditEducationForm(forms.ModelForm):
    start_date = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'type': 'month', 'class': 'outline-none border border-gray-700 bg-[#262b34] text-[#ffffff] px-2 py-2'})
    )
    end_date = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'type': 'month', 'class': 'outline-none border border-gray-700 bg-[#262b34] text-[#ffffff] px-2 py-2'})
    )
    class Meta:
        model = education
        exclude = ['user']
        
        widgets = {
            'name': forms.TextInput(attrs={'class': 'outline-none border border-gray-700 bg-[#262b34] text-[#ffffff] px-2 py-2', 'placeholder': 'Eg: Harvard University'}),
            'field_of_study': forms.TextInput(attrs={'class': 'outline-none border border-gray-700 bg-[#262b34] text-[#ffffff] px-2 py-2', 'placeholder': 'Eg: Computer Science'}),
            'degree': forms.TextInput(attrs={'class': 'outline-none border border-gray-700 bg-[#262b34] text-[#ffffff] px-2 py-2', 'placeholder': 'Eg: B.Tech'}),
            # 'start_date': forms.DateInput(attrs={'type': 'month', 'class': 'outline-none border border-black px-2 py-1'}),
            # 'end_date': forms.DateInput(attrs={'type': 'month', 'class': 'outline-none border border-black px-2 py-1', 'id':"endDate"}),
        }                                                               
        labels = {
            'name': 'University Name',
            'field_of_study': 'Course',
            'till_now': 'Currently Pursuing',
            'end_date': 'End date (or expected)',
        }
        error_messages = {
            'name': {'required':'University name is required',},
            'field_of_study': {'required': 'Enter a Valid course',}
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Format initial value to 'YYYY-MM' if data exists
        if self.instance and self.instance.start_date:
            self.initial['start_date'] = self.instance.start_date.strftime('%Y-%m')
        if self.instance and self.instance.end_date:
            self.initial['end_date'] = self.instance.end_date.strftime('%Y-%m')
            
    def clean_start_date(self):
        start_date = self.cleaned_data.get("start_date")
        print(start_date)
        if start_date:
            return datetime.strptime(start_date, "%Y-%m").date().replace(day=1)  # Convert YYYY-MM to YYYY-MM-01
        return None

    def clean_end_date(self):
        end_date = self.cleaned_data.get("end_date")
        if end_date:
            return datetime.strptime(end_date, "%Y-%m").date().replace(day=1)  # Convert YYYY-MM to YYYY-MM-01
        return None
        
class EditExperienceForm(forms.ModelForm):
    start_date = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'type': 'month', 'class': 'outline-none border border-gray-700 bg-[#262b34] text-[#ffffff] px-2 py-2'})
    )
    end_date = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'type': 'month', 'class': 'outline-none border border-gray-700 bg-[#262b34] text-[#ffffff] px-2 py-2'})
    )
    class Meta:
        model = experience
        exclude = ['user']
        labels = {
            'name': 'Company/Organization',
            'till_now': 'Currently Working',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'outline-none border border-gray-700 bg-[#262b34] text-[#ffffff] px-2 py-2', 'placeholder': 'Company Name'}),
            'role': forms.TextInput(attrs={'class': 'outline-none border border-gray-700 bg-[#262b34] text-[#ffffff] px-2 py-2', 'placeholder': 'Role'}),
            'description': forms.Textarea(attrs={'class': 'outline-none border border-gray-700 bg-[#262b34] text-[#ffffff] px-2 py-2', 'placeholder': 'Briefly Describe your Role.', 'rows': 7}),
            'till_now': forms.CheckboxInput(attrs={'id': 'exp_presentDate'})
        }
        error_messages = {
            'name': {'required':'Company name is required',},
            'role': {'required': 'Enter a Valid role',}
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Format initial value to 'YYYY-MM' if data exists
        if self.instance and self.instance.start_date:
            self.initial['start_date'] = self.instance.start_date.strftime('%Y-%m')
        if self.instance and self.instance.end_date:
            self.initial['end_date'] = self.instance.end_date.strftime('%Y-%m')
            
    def clean_start_date(self):
        start_date = self.cleaned_data.get("start_date")
        print(start_date)
        if start_date:
            return datetime.strptime(start_date, "%Y-%m").date().replace(day=1)  # Convert YYYY-MM to YYYY-MM-01
        return None

    def clean_end_date(self):
        end_date = self.cleaned_data.get("end_date")
        if end_date:
            return datetime.strptime(end_date, "%Y-%m").date().replace(day=1)  # Convert YYYY-MM to YYYY-MM-01
        return None


class EditSkillForm(forms.ModelForm):
    skills = forms.ModelMultipleChoiceField(
        queryset=skill.objects.all(),
        widget=forms.SelectMultiple(attrs={
            'class': 'select2 w-full ',
            'id': 'mySelect',
        }),
        required=False,
    )
    class Meta:
        model = userinfo
        fields = ('skills',)