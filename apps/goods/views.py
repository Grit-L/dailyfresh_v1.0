from django.shortcuts import render


# Create your views here.
def inderx(request):
    return render(request, 'login.html')
