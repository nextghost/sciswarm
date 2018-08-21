from django.shortcuts import render

def homepage(request):
    context = dict()
    return render(request, 'core/main/homepage.html', context)
