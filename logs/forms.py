from django import forms
from .models import Log, Comment

class LogForm(forms.ModelForm):
    
    class Meta:
        model = Log
        fields = ['content', 'snap_shot']
        widgets = {
            'content': forms.TextInput(attrs={
                'placeholder': "What are you working on?",
                'id': "log-input",
                'class': "flex-1 h-12 sm:h-14 bg-transparent focus:outline-none text-white placeholder-gray-500 font-mono text-sm",
                'autocomplete': "off",
                'autocorrect': "off",
                'spellcheck': "false",
                'maxlength': '280',
            }),
            'snap_shot': forms.ClearableFileInput(attrs={
                'id': 'snapshotInput',
                'accept': 'image/*',
                'onchange': 'handle_log_ImageUpload(event)',
                'class': 'hidden',
            }),
        }

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'w-full bg-[#0d1117] border border-[#30363d] rounded-lg p-3 text-sm text-gray-300 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none resize-none',
                'placeholder': 'Write a comment...',
                'rows': '3',
                'maxlength': '500',
            }),
        }
