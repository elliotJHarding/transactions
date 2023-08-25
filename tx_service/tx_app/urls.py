from django.urls import path

from .views import *


urlpatterns = [
   path('auth/createuser', CreateUser.as_view()),
   path('auth/token', obtain_auth_token),
   path('user', GetProfile.as_view()),
   path('transactions', GetTransactions.as_view()),
   path('transactions/tag', SetTransactionTag.as_view()),
   path('accounts/update', UpdateAccounts.as_view()),
   path('institutions', GetInstitutions.as_view()),
   path('requisition', Requisition.as_view()),
   path('tags', Tags.as_view()),
   path('rules', TagRules.as_view()),

   path('private/upload/transactions', UploadTransactions.as_view()),
   path('private/update/institutions', UpdateInstitutions.as_view()),
   path('private/update/links', FindLinks.as_view()),
   path('private/upload/tags', UploadTags.as_view())
]
