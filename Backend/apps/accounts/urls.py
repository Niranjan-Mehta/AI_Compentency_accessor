from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    CreateUserView,
    InviteUserView,
    LogoutView,
    ProfileView,
    RoleTokenObtainPairView,
    UserListView,
)

urlpatterns = [
    path('login/', RoleTokenObtainPairView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('create-user/', CreateUserView.as_view(), name='create_user'),
    path('invite/', InviteUserView.as_view(), name='invite_user'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('users/', UserListView.as_view(), name='user_list'),
    path('logout/', LogoutView.as_view(), name='logout'),
]
