import requests,json
from django.conf import settings
from django.core.cache import cache
from .utils import *
from .models import *
from .helper import *
from .serializers import *
from tmdb.utils import get_post
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import generics, status,permissions
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.hashers import make_password
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.utils.text import slugify
from firebase_admin import auth as firebase_auth

# Create your views here.

class SignUpView(generics.CreateAPIView):
    serializer_class = SignUpSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            "status": True,
            "log": UserProfileSerializer(user).data,
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)



    
class SignInView(generics.CreateAPIView):
    serializer_class = SignInSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)
        return Response({
            "status": True,
            "log": UserProfileSerializer(user).data,
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }, status=status.HTTP_200_OK)




class UserRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_object(self):
        return User.objects.filter(email=self.request.user.email).first()




class GetOtpView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    serializer_class = GetOtpSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        res = serializer.validated_data
        if res.get('status'):
            return Response(res, status=status.HTTP_200_OK)
        return Response(res, status=status.HTTP_400_BAD_REQUEST)




class OtpVerifyView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = VerifyOtpSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        res = serializer.validated_data
        if res.get('status'):
            try:
                user = User.objects.get(email=request.data.get('email'))
            except User.DoesNotExist:
                return Response({"status": False,"log": "User not found."}, status=status.HTTP_404_NOT_FOUND)

            refresh = RefreshToken.for_user(user)
            return Response({
                "log": UserProfileSerializer(user).data,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }, status=status.HTTP_200_OK)
        return Response(res, status=status.HTTP_400_BAD_REQUEST)
        



class ResetPasswordView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ResetPasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        res = serializer.validated_data
        if res.get('status'):
            return Response(res, status=status.HTTP_200_OK)
        return Response(res, status=status.HTTP_400_BAD_REQUEST)




class GetProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        type = request.query_params.get('type','movie')
        serializer = UserProfileSerializer(user, context={"request": request})
        data = serializer.data
        
        data['reviews'] = user.review_and_rating.count()
        data['following'] = user.following.filter(status=True).count()
        data['followers'] = user.followers.filter(status=True).count()
        data['media'] = get_post(user, type, request)
        
        return Response({"status": True, "log": data}, status=200)




class AddFollowerView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, user_id):
        user = request.user

        if str(user.id) == str(user_id):
            return Response({"status": False, "log": "You cannot follow yourself"}, status=400)

        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"status": False, "log": "User not found"}, status=404)

        if Blocks.objects.filter(blocker=user, blocked=target_user).exists():
            return Response({"status": False, "log": "You have blocked this user"}, status=400)
        if Blocks.objects.filter(blocker=target_user, blocked=user).exists():
            return Response({"status": False, "log": "This user has blocked you"}, status=400)

        follow_req, created = Follows.objects.get_or_create(
            follower=user,
            following=target_user
        )
        if not created:
            if follow_req.status:
                return Response({"status": False, "log": "You are already following this user"}, status=400)
            else:
                return Response({"status": False, "log": "Follow request already sent"}, status=400)

        # Send follow request notification
        try:
            from fcm.utils import create_and_send_notification
            follower_name = user.name or user.email.split('@')[0].title()
            title = "New Follow Request"
            message = f"{follower_name} sent you a follow request."
            create_and_send_notification(
                user=target_user,
                title=title,
                message=message,
                movie_id=None,
                media_type='movie'
            )
        except Exception as ne:
            print(f"Error sending follow request notification: {ne}")

        return Response({"status": True, "log": "Follow request sent successfully"}, status=200)





class UnFollowView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, user_id):
        user = request.user

        if str(user.id) == str(user_id):
            return Response({"status": False, "log": "You cannot unfollow yourself"}, status=400)

        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"status": False, "log": "User not found"}, status=404)

        follow_req = Follows.objects.filter(
            follower=user,
            following=target_user
        ).first()

        if not follow_req:
            return Response({"status": False, "log": "You are not following this user"}, status=400)

        follow_req.delete()

        return Response({"status": True, "log": "Unfollowed successfully"}, status=200)





class GetFollowersPendingView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        user = request.user
        follows = Follows.objects.filter(following=user, status=False).select_related('follower')
        pending_users = [f.follower for f in follows]
        serializer = UserProfileSerializer(pending_users, many=True, context={"request": request})
        return Response({"status": True, "log": serializer.data}, status=200)




class ConfirmFollowRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, user_id):
        user = request.user
        follower_user_id = user_id

        if not User.objects.filter(id=follower_user_id).exists():
            return Response({"status": False, "log": "User not found"}, status=404)

        try:
            follow_req = Follows.objects.get(follower_id=follower_user_id, following=user)
            if follow_req.status:
                return Response({"status": False, "log": "Follow request already accepted"}, status=400)

            follow_req.status = True
            follow_req.save()

            # Send follow acceptance notification
            try:
                from fcm.utils import create_and_send_notification
                accepter_name = user.name or user.email.split('@')[0].title()
                title = "Follow Request Accepted"
                message = f"{accepter_name} accepted your follow request."
                create_and_send_notification(
                    user=follow_req.follower,
                    title=title,
                    message=message,
                    movie_id=None,
                    media_type='movie'
                )
            except Exception as ne:
                print(f"Error sending follow acceptance notification: {ne}")

            return Response({"status": True, "log": "Follow request accepted"}, status=200)
        except Follows.DoesNotExist:
            return Response({"status": False, "log": "Follow request not found"}, status=404)




class GetFollowersView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        follows = Follows.objects.filter(following=request.user, status=True).select_related('follower')
        followers_list = [UserProfileSerializer(f.follower,context={"request":request}).data for f in follows]
        return Response({"status": True, "log": followers_list}, status=200)




class GetFollowingView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        target_user = request.user
        follows = Follows.objects.filter(follower=target_user, status=True).select_related('following')
        following_list = [UserProfileSerializer(f.following).data for f in follows]
        return Response({"status": True, "log": following_list}, status=200)




class FriendSuggestionsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        user = request.user
        suggested_users = get_friends_by_preferences(user)
        
        # Fallback: if no preferences match, just suggest users they don't follow and who don't follow them
        if not suggested_users:
            following_ids = set(user.following.values_list('following_id', flat=True))
            follower_ids = set(user.followers.values_list('follower_id', flat=True))
            blocked_ids = get_blocked_user_ids(user)
            excluded_ids = following_ids.union(follower_ids).union(blocked_ids)
            suggested_users = [u for u in User.objects.all() if u != user and u.id not in excluded_ids][:20]

        suggestions = [UserProfileSerializer(u,context={"request":request}).data for u in suggested_users]
        return Response({"status": True, "log": suggestions}, status=200)




class FirebaseLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        id_token = request.data.get('token')

        if not id_token:
            return Response({'status': False,'log': 'Token is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            decoded_token = firebase_auth.verify_id_token(id_token)
        except Exception as e:
            return Response({'status': False,'log': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        uid = decoded_token.get('uid')
        email = decoded_token.get('email')
        
        if not email:
            return Response({'status': False,'log': 'Email not provided by Firebase'}, status=status.HTTP_400_BAD_REQUEST)
            
        name = decoded_token.get('name')
        profile_image_url = decoded_token.get('picture')

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'name': name,
                'is_active': True,
                'password': make_password(None),
            },
        )
        if created and profile_image_url:
            img_response = requests.get(profile_image_url)
            if img_response.status_code == 200:
                file_name = f"{slugify(name or email.split('@')[0])}-profile.jpg"
                user.image.save(
                    file_name,
                    ContentFile(img_response.content),
                    save=True,
                )

            print(UserProfileSerializer(user, context={'request': request}).data)

        if user:
            token = RefreshToken.for_user(user)
            return Response({
                'access': str(token.access_token),
                'refresh': str(token),
                'log': UserProfileSerializer(user, context={'request': request}).data,
                'status': True,
                'active': user.is_active,
            }, status=status.HTTP_200_OK)
        else:
            return Response({'status': False,'log': 'Invalid or expired token'}, status=status.HTTP_400_BAD_REQUEST)


class BlockUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, user_id):
        user = request.user

        if str(user.id) == str(user_id):
            return Response({"status": False, "log": "You cannot block yourself"}, status=400)

        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"status": False, "log": "User not found"}, status=404)

        block_rel, created = Blocks.objects.get_or_create(
            blocker=user,
            blocked=target_user
        )

        if not created:
            return Response({"status": False, "log": "You have already blocked this user"}, status=400)

        # Delete any existing follows between them in either direction
        from django.db.models import Q
        Follows.objects.filter(
            Q(follower=user, following=target_user) |
            Q(follower=target_user, following=user)
        ).delete()

        return Response({"status": True, "log": "User blocked successfully"}, status=200)


class UnblockUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, user_id):
        user = request.user

        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"status": False, "log": "User not found"}, status=404)

        block_rel = Blocks.objects.filter(blocker=user, blocked=target_user).first()
        if not block_rel:
            return Response({"status": False, "log": "You have not blocked this user"}, status=400)

        block_rel.delete()
        return Response({"status": True, "log": "User unblocked successfully"}, status=200)


class BlockedUsersListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = BlocksSerializer

    def get_queryset(self):
        return Blocks.objects.filter(blocker=self.request.user)


class DeleteAccountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        password = request.data.get('password')

        if not password:
            return Response({"status": False, "log": "Password is required"}, status=status.HTTP_400_BAD_REQUEST)

        if not user.check_password(password):
            return Response({"status": False, "log": "Incorrect password"}, status=status.HTTP_400_BAD_REQUEST)

        user.delete()
        return Response({"status": True, "log": "Account deleted successfully"}, status=status.HTTP_200_OK)