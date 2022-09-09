from api import permissions, serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db.models import Avg
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken
from reviews.models import Category, Comment, Genre, Review, Title

User = get_user_model()

from .filters import TitleFilter
from .permissions import IsAuthorOrAdminOrModerator


class ListCreateDestroyViewSet(mixins.ListModelMixin,
                               mixins.CreateModelMixin,
                               mixins.DestroyModelMixin,
                               viewsets.GenericViewSet, ):
    """Кастомный вьюсет для получения списка, создания, удаления."""


class CategoryViewSet(ListCreateDestroyViewSet):
    """Получение, создание, удаление категории произведения."""
    queryset = Category.objects.all()
    serializer_class = serializers.CategorySerializer
    permission_classes = (permissions.IsAdminOrReadOnly,)
    filter_backends = (filters.SearchFilter,)
    search_fields = ('name',)
    lookup_field = 'slug'


class GenreViewSet(ListCreateDestroyViewSet):
    """Получение, создание, удаление жанра произведения."""
    queryset = Genre.objects.all()
    serializer_class = serializers.GenreSerializer
    permission_classes = (permissions.IsAdminOrReadOnly,)
    filter_backends = (filters.SearchFilter,)
    search_fields = ('name',)
    lookup_field = 'slug'


class TitleViewSet(viewsets.ModelViewSet):
    """Получение, создание, обновление, удаление произведения."""
    queryset = Title.objects.all().annotate(Avg('reviews__score')).order_by(
        'name')
    serializer_class = serializers.TitleSerializer
    permission_classes = (permissions.IsAdminOrReadOnly,)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = TitleFilter

    def get_serializer_class(self):
        if self.action in ('retrieve', 'list'):
            return serializers.TitleReadSerializer
        return serializers.TitleSerializer


class UserSignUp(APIView):
    """Регистрация пользователя."""

    permission_classes = (AllowAny,)

    def send_confirmation_code(self, user):
        """Отправка кода на email."""
        token = default_token_generator.make_token(user)

        send_mail(
            subject='Confirmation code',
            message=f'Ваш код: {token}',
            from_email='robot@yamdb.ru',
            recipient_list=[user.email]
        )

    def post(self, request):
        serializer = serializers.UserSignUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        self.send_confirmation_code(user)
        return Response(serializer.data, status.HTTP_200_OK)


class UserToken(APIView):
    """Получение токена."""
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = serializers.TokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = get_object_or_404(User, username=request.data['username'])

        if default_token_generator.check_token(
                user, request.data['confirmation_code']
        ):
            token = AccessToken.for_user(user)
            return Response(
                {'token': str(token)}, status=status.HTTP_200_OK
            )
        return Response(
            {'Ошибка формирования токена'},
            status=status.HTTP_400_BAD_REQUEST
        )


class UserViewSet(viewsets.ModelViewSet):
    """Вьюсет для добавления/изменения/удаления пользователей."""

    queryset = User.objects.all()
    serializer_class = serializers.UsersSerializer
    permission_classes = (permissions.IsAdmin,)
    filter_backends = (filters.SearchFilter,)
    search_fields = ('username',)
    lookup_field = 'username'

    @action(methods=['GET', 'PATCH'], detail=False, permission_classes=(IsAuthenticated,))
    def me(self, request):
        serializer = serializers.UsersSerializer(request.user)
        if request.method == 'PATCH':
            serializer = serializers.UsersMeSerializer(
                request.user,
                data=request.data,
                partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.data)


class ReviewViewSet(viewsets.ModelViewSet):
    """Получение, создание, обновление, удаление отзыва."""
    serializer_class = serializers.ReviewSerializer
    permission_classes = (IsAuthorOrAdminOrModerator,)

    def get_queryset(self):
        title_id = self.kwargs.get('title_id')
        title = get_object_or_404(Title, pk=title_id)
        new_queryset = title.reviews.all()

        return new_queryset

    def perform_create(self, serializer):
        title_id = self.kwargs.get('title_id')
        title = get_object_or_404(Title, id=title_id)
        serializer.save(author=self.request.user, title=title)


class CommentViewSet(viewsets.ModelViewSet):
    """Получение, создание, обновление, удаление комментария."""
    serializer_class = serializers.CommentSerializer
    permission_classes = (IsAuthorOrAdminOrModerator,)

    def get_queryset(self):
        review_id = self.kwargs.get('review_id')
        review = get_object_or_404(Review, pk=review_id)
        new_queryset = review.comments.all()

        return new_queryset

    def perform_create(self, serializer):
        review_id = self.kwargs.get('review_id')
        review = get_object_or_404(Review, pk=review_id)
        serializer.save(author=self.request.user, review=review)
