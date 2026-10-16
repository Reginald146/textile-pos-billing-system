from decimal import Decimal
from django.db.models.functions import TruncDate
from django.db.models import Sum, Count
from datetime import timedelta
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from .models import Product, Sale, SaleItem, Supplier, ProductReturn

def home(request):
    return render(request, "pos/home.html")




def _login_portal(request, portal):
    is_admin_portal = portal == "admin"

    if request.user.is_authenticated:
        correct_role = (
            request.user.is_superuser
            if is_admin_portal
            else not request.user.is_superuser
        )

        if correct_role:
            return redirect(
                "dashboard" if is_admin_portal else "staff_dashboard"
            )

        logout(request)
        messages.info(request, "Please sign in with the correct account.")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is None:
            messages.error(request, "Invalid username or password.")

        elif is_admin_portal and not user.is_superuser:
            messages.error(
                request,
                "This account is not authorized for Admin Login."
            )

        elif not is_admin_portal and user.is_superuser:
            messages.error(
                request,
                "Please use Admin Login for this account."
            )

        else:
            login(request, user)
            return redirect(
                "dashboard" if is_admin_portal else "staff_dashboard"
            )

    return render(request, "pos/login.html", {
        "portal_title": (
            "Admin Sign In" if is_admin_portal else "Staff Sign In"
        ),
    })



def admin_login(request):
    return _login_portal(request, "admin")


def staff_login(request):
    return _login_portal(request, "staff")


# Logout
@login_required
def logout_page(request):
    logout(request)
    return redirect("/")


# Admin Dashboard
@login_required
def dashboard(request):
    if not request.user.is_superuser:
        return redirect("billing")

    products_count = Product.objects.count()
    return render(
        request,
        "pos/dashboard.html",
        {"products_count": products_count},
    )



@login_required
def staff_dashboard(request):
    if request.user.is_superuser:
        return redirect("dashboard")

    return render(request, "pos/staff_dashboard.html")



#Product Management

@login_required
def products(request):
    if not request.user.is_superuser:
        return redirect("billing")

    if request.method == "POST":
        action = request.POST.get("action", "")

        
        if action == "delete":
            product_id = request.POST.get("product_id")
            product = get_object_or_404(Product, id=product_id)

            try:
                product.delete()
                messages.success(request, "Product deleted successfully.")
            except Exception:
                messages.error(
                    request,
                    "This product cannot be deleted because it may be linked to existing sales."
                )

            return redirect("products")

        product_id = request.POST.get("product_id")
        name = request.POST.get("name", "").strip()
        sku = request.POST.get("sku", "").strip()
        category = request.POST.get("category", "").strip()
        size = request.POST.get("size", "").strip()
        color = request.POST.get("color", "").strip()
        price = request.POST.get("price", "").strip()
        stock_quantity = request.POST.get("stock_quantity", "").strip()
        supplier_id = request.POST.get("supplier", "").strip()

        if not name or not sku or not price or not stock_quantity:
            messages.error(request, "Please fill in all required fields.")
            return redirect("products")

        try:
            price_value = Decimal(price)
            stock_value = int(stock_quantity)

            if price_value < 0 or stock_value < 0:
                raise ValueError

            if price_value.as_tuple().exponent < -2:
                raise ValueError

        except (ValueError, ArithmeticError):
            messages.error(
                request,
                "Enter a valid price with up to 2 decimal places and a non-negative whole-number stock quantity."
            )
            return redirect("products")

        if Product.objects.filter(sku=sku).exclude(id=product_id or None).exists():
            messages.error(request, "A product with this SKU already exists.")
            return redirect("products")

        supplier = None
        if supplier_id:
            supplier = get_object_or_404(Supplier, id=supplier_id)

        if product_id:
            product = get_object_or_404(Product, id=product_id)
            product.name = name
            product.sku = sku
            product.category = category
            product.size = size
            product.color = color
            product.price = price_value
            product.stock_quantity = stock_value
            product.supplier = supplier
            product.save()
            messages.success(request, "Product updated successfully.")
        else:
            Product.objects.create(
                name=name,
                sku=sku,
                category=category,
                size=size,
                color=color,
                price=price_value,
                stock_quantity=stock_value,
                supplier=supplier,
            )
            messages.success(request, "Product added successfully.")

        return redirect("products")

    products_list = Product.objects.select_related("supplier").order_by("name")
    suppliers_list = Supplier.objects.order_by("name")

    return render(request, "pos/products.html", {
        "products": products_list,
        "suppliers": suppliers_list,
    })



# Staff Management


@login_required
def staff_management(request):
    if not request.user.is_superuser:
        return redirect("billing")

    if request.method == "POST":
        action = request.POST.get("action", "")

        # Activate or deactivate an existing staff account
        if action in ("deactivate", "activate"):
            staff_id = request.POST.get("staff_id")

            member = get_object_or_404(
                User,
                id=staff_id,
                is_superuser=False,
                is_staff=False,
            )

            member.is_active = (action == "activate")
            member.save(update_fields=["is_active"])

            status = "activated" if member.is_active else "deactivated"
            messages.success(
                request,
                f"Staff account '{member.username}' has been {status}."
            )
            return redirect("staff_management")

        # Create a new staff account
        full_name = request.POST.get("full_name", "").strip()
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        if not full_name or not username or not password:
            messages.error(request, "Please fill in all fields.")
        elif User.objects.filter(username=username).exists():
            messages.error(request, "That username already exists.")
        elif len(password) < 8:
            messages.error(request, "Password must contain at least 8 characters.")
        else:
            name_parts = full_name.split()

            User.objects.create_user(
                username=username,
                password=password,
                first_name=name_parts[0],
                last_name=" ".join(name_parts[1:]),
                is_staff=False,
                is_active=True,
            )

            messages.success(
                request,
                f"Staff account '{username}' created successfully."
            )
            return redirect("staff_management")

    staff_members = User.objects.filter(
        is_superuser=False,
        is_staff=False
    ).order_by("username")

    return render(request, "pos/staff_management.html", {
        "staff_members": staff_members,
    })




# Supplier Management

@login_required
def suppliers(request):
    if not request.user.is_superuser:
        return redirect("billing")

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "delete":
            supplier_id = request.POST.get("supplier_id")
            supplier = get_object_or_404(Supplier, id=supplier_id)
            supplier.delete()
            messages.success(request, "Supplier deleted successfully.")
            return redirect("suppliers")

        supplier_id = request.POST.get("supplier_id", "").strip()
        name = request.POST.get("name", "").strip()
        phone = request.POST.get("phone", "").strip()
        email = request.POST.get("email", "").strip()
        address = request.POST.get("address", "").strip()

        if not name:
            messages.error(request, "Supplier name is required.")
            return redirect("suppliers")

        if len(name) > 150 or len(phone) > 20:
            messages.error(request, "Name or phone number is too long.")
            return redirect("suppliers")

        if len(email) > 254:
            messages.error(request, "Email address is too long.")
            return redirect("suppliers")

        try:
            if supplier_id:
                supplier = get_object_or_404(Supplier, id=supplier_id)
                supplier.name = name
                supplier.phone = phone
                supplier.email = email
                supplier.address = address
                supplier.save()
                messages.success(request, "Supplier updated successfully.")
            else:
                Supplier.objects.create(
                    name=name,
                    phone=phone,
                    email=email,
                    address=address,
                )
                messages.success(request, "Supplier added successfully.")

        except Exception:
            messages.error(
                request,
                "Could not save the supplier. Please check the details."
            )

        return redirect("suppliers")

    suppliers_list = Supplier.objects.order_by("name")

    return render(request, "pos/suppliers.html", {
        "suppliers": suppliers_list,
    })



# Product Returns

@login_required
def returns(request):
    if not request.user.is_superuser:
        return redirect("billing")

    if request.method == "POST":
        try:
            sale_item_id = int(request.POST.get("sale_item_id", ""))
            quantity = int(request.POST.get("quantity", ""))
        except (ValueError, TypeError):
            messages.error(request, "Select a valid sale item and quantity.")
            return redirect("returns")

        if quantity < 1:
            messages.error(request, "Return quantity must be at least 1.")
            return redirect("returns")

        with transaction.atomic():
            sale_item = get_object_or_404(
                SaleItem.objects.select_related("product", "sale").select_for_update(),
                id=sale_item_id,
            )

            already_returned = (
                ProductReturn.objects
                .filter(sale_item=sale_item)
                .aggregate(total=Sum("quantity"))["total"] or 0
            )
            remaining = sale_item.quantity - already_returned

            if quantity > remaining:
                messages.error(
                    request,
                    f"Only {remaining} unit(s) remain eligible for return."
                )
                return redirect("returns")

            refund = sale_item.unit_price * quantity

            ProductReturn.objects.create(
                sale_item=sale_item,
                quantity=quantity,
                refund_amount=refund,
                reason=request.POST.get("reason", "").strip()[:250],
                processed_by=request.user,
            )

            product = sale_item.product
            product.stock_quantity += quantity
            product.save(update_fields=["stock_quantity"])

        messages.success(
            request,
            f"Return recorded. Refund amount: ₹{refund:.2f}. Stock updated."
        )
        return redirect("returns")

    sale_items = (
        SaleItem.objects
        .select_related("sale", "product")
        .order_by("-sale__created_at")
    )

    returnable_items = []
    for item in sale_items:
        returned = (
            ProductReturn.objects
            .filter(sale_item=item)
            .aggregate(total=Sum("quantity"))["total"] or 0
        )
        item.remaining_quantity = item.quantity - returned

        if item.remaining_quantity > 0:
            returnable_items.append(item)

    return_records = (
        ProductReturn.objects
        .select_related(
            "sale_item__sale",
            "sale_item__product",
            "processed_by",
        )
        .order_by("-created_at")
    )

    return render(request, "pos/returns.html", {
        "returnable_items": returnable_items,
        "return_records": return_records,
    })



# Billing Transactions

@login_required
def transactions(request):
    if not request.user.is_superuser:
        return redirect("billing")

    sales = Sale.objects.select_related("cashier").order_by("-created_at")

    payment_method = request.GET.get("payment", "").strip()
    search = request.GET.get("search", "").strip()

    if payment_method in ["CASH", "CARD", "UPI"]:
        sales = sales.filter(payment_method=payment_method)

    if search:
        if search.isdigit():
            sales = sales.filter(id=int(search))
        else:
            sales = sales.filter(customer_name__icontains=search)

    return render(request, "pos/transactions.html", {
        "sales": sales,
        "selected_payment": payment_method,
        "search": search,
    })



# Ledger and Reports

@login_required
def reports(request):
    if not request.user.is_superuser:
        return redirect("billing")

    today = timezone.localdate()
    week_start = today - timedelta(days=6)

    # Overall sales summary
    sales_summary = Sale.objects.aggregate(
        total_revenue=Sum("total"),
        total_bills=Count("id"),
    )

    # Total units sold, excluding returned units for now
    total_units_sold = (
        SaleItem.objects.aggregate(total=Sum("quantity"))["total"] or 0
    )

    # Sales grouped by payment method
    payment_summary = (
        Sale.objects.values("payment_method")
        .annotate(
            total=Sum("total"),
            bill_count=Count("id"),
        )
        .order_by("payment_method")
    )

    # Daily sales for the last seven days
    daily_sales = (
        Sale.objects.filter(
            created_at__date__gte=week_start,
            created_at__date__lte=today,
        )
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            total=Sum("total"),
            bill_count=Count("id"),
        )
        .order_by("day")
    )

    # Most recent transactions
    recent_sales = (
        Sale.objects.select_related("cashier")
        .order_by("-created_at")[:20]
    )

    context = {
        "total_revenue": sales_summary["total_revenue"] or 0,
        "total_bills": sales_summary["total_bills"] or 0,
        "total_units_sold": total_units_sold,
        "payment_summary": payment_summary,
        "daily_sales": daily_sales,
        "recent_sales": recent_sales,
        "week_start": week_start,
        "today": today,
    }

    return render(request, "pos/reports.html", context)



# Billing Page
@login_required
def billing_page(request):
    products = Product.objects.filter(
        stock_quantity__gt=0
    ).order_by("name")

    return render(
        request,
        "pos/billing.html",
        {"products": products},
    )


# Create Sale
@login_required
def create_sale(request):
    if request.method != "POST":
        return redirect("billing")

    product_ids = request.POST.getlist("product_id")
    quantities = request.POST.getlist("quantity")
    customer_name = request.POST.get("customer_name", "").strip()
    payment_method = request.POST.get("payment_method", "CASH")

    if payment_method not in ["CASH", "CARD", "UPI"]:
        messages.error(request, "Invalid payment method.")
        return redirect("billing")

    try:
        with transaction.atomic():
            selected_items = []
            subtotal = Decimal("0.00")

            if len(product_ids) != len(quantities):
                raise ValueError("Invalid billing items.")

            for product_id, quantity in zip(product_ids, quantities):
                if not product_id:
                    raise ValueError("Please select a product.")

                qty = int(quantity)

                if qty <= 0:
                    raise ValueError(
                        "Quantity must be greater than zero."
                    )

                product = Product.objects.select_for_update().get(
                    pk=int(product_id)
                )

                if product.stock_quantity < qty:
                    raise ValueError(
                        f"Not enough stock for {product.name}. "
                        f"Available: {product.stock_quantity}"
                    )

                line_total = product.price * qty
                subtotal += line_total
                selected_items.append((product, qty, line_total))

            if not selected_items:
                raise ValueError("Please select at least one product.")

            sale = Sale.objects.create(
                cashier=request.user,
                customer_name=customer_name,
                subtotal=subtotal,
                discount=Decimal("0.00"),
                total=subtotal,
                payment_method=payment_method,
            )

            for product, qty, line_total in selected_items:
                SaleItem.objects.create(
                    sale=sale,
                    product=product,
                    quantity=qty,
                    unit_price=product.price,
                    line_total=line_total,
                )

                product.stock_quantity -= qty
                product.save(update_fields=["stock_quantity"])

        return redirect("bill_detail", sale_id=sale.id)

    except (ValueError, Product.DoesNotExist, TypeError):
        messages.error(
            request,
            "Could not complete the sale. Check the selected products "
            "and quantities, then try again.",
        )
        return redirect("billing")


# Printable Bill
@login_required
def bill_detail(request, sale_id):
    sale = get_object_or_404(
        Sale.objects.prefetch_related("items__product"),
        pk=sale_id,
    )

    if not (
        request.user.is_superuser
        or request.user.is_staff
        or sale.cashier_id == request.user.id
    ):
        return redirect("billing")

    return render(
        request,
        "pos/bill_detail.html",
        {"sale": sale},
    )


# Logout
@login_required
def logout_page(request):
    logout(request)
    return redirect("/")


# Admin Dashboard
@login_required
def dashboard(request):
    if not (request.user.is_superuser or request.user.is_staff):
        return redirect("billing")

    products_count = Product.objects.count()
    return render(
        request,
        "pos/dashboard.html",
        {"products_count": products_count},
    )


# Billing Page
@login_required
def billing_page(request):
    products = Product.objects.filter(
        stock_quantity__gt=0
    ).order_by("name")

    return render(
        request,
        "pos/billing.html",
        {"products": products},
    )


# Create Sale
@login_required
def create_sale(request):
    if request.method != "POST":
        return redirect("billing")

    product_ids = request.POST.getlist("product_id")
    quantities = request.POST.getlist("quantity")
    customer_name = request.POST.get("customer_name", "").strip()
    payment_method = request.POST.get("payment_method", "CASH")

    if payment_method not in ["CASH", "CARD", "UPI"]:
        messages.error(request, "Invalid payment method.")
        return redirect("billing")

    try:
        with transaction.atomic():
            selected_items = []
            subtotal = Decimal("0.00")

            if len(product_ids) != len(quantities):
                raise ValueError("Invalid billing items.")

            for product_id, quantity in zip(product_ids, quantities):
                if not product_id:
                    raise ValueError("Please select a product.")

                qty = int(quantity)

                if qty <= 0:
                    raise ValueError(
                        "Quantity must be greater than zero."
                    )

                product = Product.objects.select_for_update().get(
                    pk=int(product_id)
                )

                if product.stock_quantity < qty:
                    raise ValueError(
                        f"Not enough stock for {product.name}. "
                        f"Available: {product.stock_quantity}"
                    )

                line_total = product.price * qty
                subtotal += line_total
                selected_items.append((product, qty, line_total))

            if not selected_items:
                raise ValueError("Please select at least one product.")

            sale = Sale.objects.create(
                cashier=request.user,
                customer_name=customer_name,
                subtotal=subtotal,
                discount=Decimal("0.00"),
                total=subtotal,
                payment_method=payment_method,
            )

            for product, qty, line_total in selected_items:
                SaleItem.objects.create(
                    sale=sale,
                    product=product,
                    quantity=qty,
                    unit_price=product.price,
                    line_total=line_total,
                )

                product.stock_quantity -= qty
                product.save(update_fields=["stock_quantity"])

        return redirect("bill_detail", sale_id=sale.id)

    except (ValueError, Product.DoesNotExist, TypeError):
        messages.error(
            request,
            "Could not complete the sale. Check the selected products "
            "and quantities, then try again.",
        )
        return redirect("billing")


# Printable Bill
@login_required
def bill_detail(request, sale_id):
    sale = get_object_or_404(
        Sale.objects.prefetch_related("items__product"),
        pk=sale_id,
    )

    if not (
        request.user.is_superuser
        or request.user.is_staff
        or sale.cashier_id == request.user.id
    ):
        return redirect("billing")

    return render(
        request,
        "pos/bill_detail.html",
        {"sale": sale},
    )
