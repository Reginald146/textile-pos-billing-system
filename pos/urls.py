from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("admin-login/", views.admin_login, name="admin_login"),
    path("staff-login/", views.staff_login, name="staff_login"),
    path("logout/", views.logout_page, name="logout"),
    path("staff-dashboard/", views.staff_dashboard, name="staff_dashboard"),

     # Admin management modules
    path("products/", views.products, name="products"),
    path("staff-management/", views.staff_management, name="staff_management"),
    path("suppliers/", views.suppliers, name="suppliers"),
    path("returns/", views.returns, name="returns"),
    path("transactions/", views.transactions, name="transactions"),
    path("reports/", views.reports, name="reports"),
    # Billing modules
    path("billing/", views.billing_page, name="billing"),
    path("billing/create/", views.create_sale, name="create_sale"),
    path("bill/<int:sale_id>/", views.bill_detail, name="bill_detail"),
]
