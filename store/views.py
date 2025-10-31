from django.shortcuts import render, get_object_or_404, redirect
from .models import Product, ReviwRating
from category.models import Category
from carts.models import CartItem
from carts.views import _cart_id
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from .forms import ReviewForm
from django.contrib import messages
from orders.models import OrderProduct
from django.http import JsonResponse
from django.db.models import Min, Max

# Create your views here.
def store(request, category_slug=None):

    categories = None
    products = None
    if category_slug != None:
        categories = get_object_or_404(Category, slug=category_slug)
        products = Product.objects.filter(category=categories, is_available=True).order_by('id')
        paginator = Paginator(products, 5)
        page = request.GET.get('page')
        paged_products = paginator.get_page(page)
        product_count = products.count()
    else:
        products = Product.objects.all().filter(is_available=True).order_by('id')
        paginator = Paginator(products, 5)
        page = request.GET.get('page')
        paged_products = paginator.get_page(page)
        product_count = products.count() 

    price_range = Product.objects.filter(is_available=True).aggregate(
        min_price=Min('price'),
        max_price=Max('price')
    )

    context = {
        'products': paged_products,
        'product_count': product_count,
        'min_price': price_range['min_price'] or 0,
        'max_price': price_range['max_price'] or 100000000,
        
    }
    return render(request, 'store/store.html', context)



def product_detail(request, category_slug, product_slug):

    try:
        single_product = Product.objects.get(category__slug=category_slug, slug=product_slug)
        in_cart = CartItem.objects.filter(cart__cart_id=_cart_id(request), product=single_product).exists()
    except Exception as e:
        raise e


    if request.user.is_authenticated:
        try:
            orderproduct = OrderProduct.objects.filter(user=request.user, product_id=single_product.id).exists()
        except OrderProduct.DoesNotExist:
            orderproduct = None
    else:
        orderproduct = None

    reviews = ReviwRating.objects.filter(product_id=single_product.id, status = True)

    context = {
        'single_product': single_product,
        'in_cart': in_cart,
        'orderproduct': orderproduct,
        'reviews': reviews,
    }

    return render(request, 'store/product_detail.html', context)



def search(request):
    if 'keyword' in request.GET:
        keyword = request.GET['keyword']
        if keyword:
            products = Product.objects.order_by('-created_date').filter(Q(description__icontains=keyword) | Q(product_name__icontains=keyword))
            product_count = products.count()

    context = {
        'products': products,
        'product_count': product_count,
    }

    return render(request, 'store/store.html', context)


def submit_review(request, product_id):
    url = request.META.get('HTTP_REFERER')
    if request.method == 'POST':
        try:
            # Si el usuario ya dejó una reseña, se actualiza
            reviews = ReviwRating.objects.get(user__id=request.user.id, product__id=product_id)
            form = ReviewForm(request.POST, instance=reviews)
            form.save()
            messages.success(request, 'Muchas gracias! Tu comentario ha sido actualizado')
            return redirect(url)

        except ReviwRating.DoesNotExist:
            # Si no existe, se crea una nueva reseña
            form = ReviewForm(request.POST)
            if form.is_valid():
                data = ReviwRating()
                data.subject = form.cleaned_data['subject']
                data.rating = form.cleaned_data['rating']
                data.review = form.cleaned_data['review']
                data.ip = request.META.get('REMOTE_ADDR')
                data.product_id = product_id
                data.user_id = request.user.id
                data.save()
                messages.success(request, 'Muchas gracias, tu comentario fue enviado con exito!')
                return redirect(url)

def get_price_range_api(request):
    """API para obtener rango de precios"""
    try:
        price_range = Product.objects.filter(is_available=True).aggregate(
            min_price=Min('price'),
            max_price=Max('price')
        )
        
        return JsonResponse({
            'success': True,
            'min_price': price_range['min_price'] or 0,
            'max_price': price_range['max_price'] or 1000000
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def filter_products_by_price(request):
    """Filtra productos por rango de precios"""
    try:
        min_price = request.GET.get('min_price', 0)
        max_price = request.GET.get('max_price', 1000000)
        category_slug = request.GET.get('category_slug', '')
        
        # Convertir a enteros
        try:
            min_price = int(min_price)
            max_price = int(max_price)
        except (ValueError, TypeError):
            min_price = 0
            max_price = 1000000
        
        # Construir query base
        products = Product.objects.filter(
            is_available=True,
            price__gte=min_price,
            price__lte=max_price
        )
        
        # Filtrar por categoría si se especifica
        if category_slug and category_slug != 'all':
            products = products.filter(category__slug=category_slug)
        
        # Serializar productos
        products_data = []
        for product in products:
            products_data.append({
                'id': product.id,
                'name': product.product_name,
                'price': product.price,
                'formatted_price': f"Gs. {product.price:,}",
                'stock': product.stock,
                'image_url': product.images.url if product.images else '/static/images/default-product.jpg',
                'category': product.category.category_name,
                'url': product.get_url(),
                'add_to_cart_url': f"/cart/add/{product.id}/"
            })
        
        return JsonResponse({
            'success': True,
            'products': products_data,
            'count': len(products_data),
            'min_price': min_price,
            'max_price': max_price
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})