from django.shortcuts import render, redirect
from django.http import HttpResponse
from .forms import RegisterForm
from .models import Account
from django.contrib import messages
from django.contrib import auth
from django.contrib.auth.decorators import login_required
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import EmailMessage
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from django.urls import reverse
from urllib.parse import urlencode
from carts.views import _cart_id, cart
from carts.models import Cart, CartItem
import requests

account_activation_token = PasswordResetTokenGenerator()
# Create your views here.
def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
                messages.error(request, 'Email settings are not configured. Please contact the site administrator.')
                return render(request, 'accounts/register.html', {'form': form})

            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            phone_no = form.cleaned_data['phone_no']
            username = email.split('@')[0]

            user = Account.objects.create_user(
                first_name=first_name,
                last_name=last_name,
                username=username,
                email=email,
                password=password,
                phone_no=phone_no,
            )

            user.save()

            # USER AUTHENTICATION
            current_site = get_current_site(request)
            mail_subject = 'Kindly confirm your registration'
            message = render_to_string('accounts/account_verification_email.html',{
                'user' : user,
                'domain' : current_site.domain,
                'uid' : urlsafe_base64_encode(force_bytes(user.pk)),
                'token' : account_activation_token.make_token(user),
            })

            to_email = email
            send_mail = EmailMessage(
                mail_subject,
                message,
                from_email=settings.EMAIL_HOST_USER,
                to=[to_email],
            )
            
            send_mail.content_subtype = "html" 
            send_mail.send()

            # messages.success(
            #     request,
            #     f'Verification email sent to {email}. Please check your inbox to verify your account.',
            # )
            login_url = reverse('login')
            query_string = urlencode({'command': 'verification', 'email': email})
            return redirect(f'{login_url}?{query_string}')

    else:
        form = RegisterForm()
    context = {
        'form': form,
    }
    return render(request, 'accounts/register.html', context)

def login(request):
    if request.method == 'POST':
        email = request.POST['email']
        password = request.POST['password']
        user = auth.authenticate(request, email=email, password=password)
        if user is not None:
            cart_id = _cart_id(request)
            auth.login(request, user)

            cart = Cart.objects.filter(cart_id=cart_id).first()
            if cart is not None:
                cart.cart_id = _cart_id(request)
                cart.save(update_fields=['cart_id'])

                guest_items = CartItem.objects.filter(cart=cart, user__isnull=True)
                for guest_item in guest_items:
                    guest_variation_ids = set(guest_item.variations.values_list('id', flat=True))
                    matching_item = None

                    user_items = CartItem.objects.filter(
                        user=user,
                        product=guest_item.product,
                        is_active=True,
                    ).exclude(pk=guest_item.pk)
                    for user_item in user_items:
                        user_variation_ids = set(user_item.variations.values_list('id', flat=True))
                        if user_variation_ids == guest_variation_ids:
                            matching_item = user_item
                            break

                    if matching_item is not None:
                        matching_item.quantity += guest_item.quantity
                        matching_item.save(update_fields=['quantity'])
                        guest_item.delete()
                    else:
                        guest_item.user = user
                        guest_item.save(update_fields=['user'])

            messages.success(request, 'Login successful! Welcome back!')
            url = request.META.get('HTTP_REFERER')
            try:
                query = requests.utils.urlparse(url).query
                params = dict(x.split('=') for x in query.split('&'))
                if 'next' in params:
                    nextPage = params['next']
                    return redirect(nextPage)
                
            except:
                return redirect('dashboard')

        else:
            messages.success(request, 'Invalid Credentials: Please check your email and password and try again.')


    return render(request, 'accounts/login.html')

@login_required(login_url='login')
def logout(request):   
    auth.logout(request)
    return redirect('login')

def activate(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = Account._default_manager.get(pk=uid)

    except (TypeError, ValueError, OverflowError, Account.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, 'Account activated successfully')
        return redirect('login')

    else:
        messages.error(request, 'Invalid activation link')    
        return redirect('register')

@login_required(login_url='login')
def dashboard(request):
    return render(request, 'accounts/dashboard.html')


def forgotPassword(request):
    if request.method == 'POST':
        email = request.POST['email']
        user = Account.objects.filter(email__iexact=email).first()

        if user:
            current_site = get_current_site(request)
            mail_subject = 'Reset your password'
            message = render_to_string('accounts/reset_password_email.html', {
                'user': user,
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': account_activation_token.make_token(user),
            })
            
            to_email = email
            send_mail = EmailMessage(
                mail_subject,
                message,
                from_email=settings.EMAIL_HOST_USER,
                to=[to_email],
            )
            # THIS LINE FIXES THE ISSUE:
            send_mail.content_subtype = "html"  
            
            send_mail.send()

            messages.success(request, 'A reset password link has been sent to your email address. Please check your inbox to reset your password.')
            return redirect('login')
        else:
            messages.error(request, 'This email does not exist. Kindly enter a valid email address.')
            return render(request, 'accounts/forgotPassword.html')
            
    return render(request, 'accounts/forgotPassword.html')

def resetpassword_validate(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = Account._default_manager.get(pk=uid)

    except (TypeError, ValueError, OverflowError, Account.DoesNotExist):
        messages.error(request, 'This link has been expired. Please request a new one.')
        return redirect('forgotPassword')

    if user is not None and default_token_generator.check_token(user, token):
        request.session['uid'] = uid
        messages.success(request, 'Your request has been validated. Please enter your new password.')
        return redirect('resetPassword')

    else:
        messages.error(request, 'This link has been expired. Please request a new one.')
        return redirect('forgetPassword')

def resetPassword(request):
    if request.method == 'POST':
        new_password = request.POST['new_password']
        confirm_password = request.POST['confirm_password']

        if new_password == confirm_password:
            user = Account.objects.get(pk=request.session['uid'])
            uid = request.session['uid']
            user.set_password(new_password)
            user.save()
            messages.success(request, 'Your password has been reset successfully.')
            return redirect('login')

        else:
            messages.error(request, 'Passwords do not match. Please try again.')
            return render(request, 'accounts/resetPassword.html')
    return render(request, 'accounts/resetPassword.html')
