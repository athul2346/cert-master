from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import login
from .serializers import LoginSerializer, CompanySignupSerializer

class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        login(request, user)

        return Response(
            {
                "message": "Login successful",
                "email": user.email
            },
            status=status.HTTP_200_OK
        )


class CompanySignupView(APIView):
    permission_classes = []

    def post(self, request):
        serializer = CompanySignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                "message": "Company registered successfully",
                "email": user.email,
            },
            status=status.HTTP_201_CREATED,
        )