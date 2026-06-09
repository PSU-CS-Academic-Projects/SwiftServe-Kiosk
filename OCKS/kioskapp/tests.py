from django.test import TestCase
from django.urls import reverse
from kioskapp.models import Customer

class CustomerRegistrationTests(TestCase):
    def setUp(self):
        self.register_url = reverse('customer_register')

    def test_registration_success(self):
        """Test successful registration with all valid fields, including email."""
        response = self.client.post(self.register_url, {
            'name': 'Test User',
            'phone_number': '09123456789',
            'email': 'test@example.com',
            'password': 'password123',
            'confirm_password': 'password123',
        })
        self.assertRedirects(response, reverse('home_page'))
        self.assertTrue(Customer.objects.filter(phone_number='09123456789').exists())
        customer = Customer.objects.get(phone_number='09123456789')
        self.assertEqual(customer.email, 'test@example.com')

    def test_registration_missing_email(self):
        """Test registration fails when email is missing."""
        response = self.client.post(self.register_url, {
            'name': 'Test User No Email',
            'phone_number': '09123456780',
            'email': '',
            'password': 'password123',
            'confirm_password': 'password123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('errors', response.context)
        self.assertEqual(response.context['errors'].get('email'), 'Email is required')
        self.assertFalse(Customer.objects.filter(phone_number='09123456780').exists())

    def test_registration_duplicate_phone(self):
        """Test registration fails with a phone number that already exists."""
        Customer.objects.create(
            name='Existing User',
            phone_number='09111111111',
            email='existing@example.com',
            password='hashedpassword'
        )
        response = self.client.post(self.register_url, {
            'name': 'New User',
            'phone_number': '09111111111',
            'email': 'new@example.com',
            'password': 'password123',
            'confirm_password': 'password123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('errors', response.context)
        self.assertEqual(response.context['errors'].get('phone_number'), 'This phone number is already registered')

    def test_registration_duplicate_email(self):
        """Test registration fails with an email address that already exists."""
        Customer.objects.create(
            name='Existing User',
            phone_number='09111111111',
            email='existing@example.com',
            password='hashedpassword'
        )
        response = self.client.post(self.register_url, {
            'name': 'New User',
            'phone_number': '09222222222',
            'email': 'existing@example.com',
            'password': 'password123',
            'confirm_password': 'password123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('errors', response.context)
        self.assertEqual(response.context['errors'].get('email'), 'This email is already registered')

    def test_registration_password_mismatch(self):
        """Test registration fails when password and confirm password do not match."""
        response = self.client.post(self.register_url, {
            'name': 'Mismatched User',
            'phone_number': '09333333333',
            'email': 'mismatch@example.com',
            'password': 'password123',
            'confirm_password': 'differentpassword',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('errors', response.context)
        self.assertEqual(response.context['errors'].get('confirm_password'), 'Passwords do not match')

    def test_registration_short_password(self):
        """Test registration fails when the password is less than 6 characters."""
        response = self.client.post(self.register_url, {
            'name': 'Short Password User',
            'phone_number': '09444444444',
            'email': 'short@example.com',
            'password': '12345',
            'confirm_password': '12345',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('errors', response.context)
        self.assertEqual(response.context['errors'].get('password'), 'Password must be at least 6 characters')


from kioskapp.models import Order, Payment

class OrderStatusAccessTests(TestCase):
    def setUp(self):
        self.customer_a = Customer.objects.create(
            name="Customer A",
            phone_number="09111111111",
            email="a@example.com",
            password="password123"
        )
        self.customer_b = Customer.objects.create(
            name="Customer B",
            phone_number="09222222222",
            email="b@example.com",
            password="password123"
        )
        self.order_a = Order.objects.create(
            order_type="take_out",
            total_price=10.00,
            queue_number=101,
            status="Pending",
            customer=self.customer_a
        )
        self.payment_a = Payment.objects.create(
            order=self.order_a,
            method="cash",
            amount_paid=10.00,
            payment_status="Pending"
        )
        self.order_guest = Order.objects.create(
            order_type="take_out",
            total_price=15.00,
            queue_number=102,
            status="Pending",
            customer=None
        )
        self.payment_guest = Payment.objects.create(
            order=self.order_guest,
            method="cash",
            amount_paid=15.00,
            payment_status="Pending"
        )

    def test_anonymous_access_guest_order(self):
        """An anonymous user can access a guest order status."""
        url = reverse('order_status', kwargs={'pk': self.order_guest.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_anonymous_access_customer_order_fails(self):
        """An anonymous user cannot access a customer order status."""
        url = reverse('order_status', kwargs={'pk': self.order_a.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_customer_access_own_order(self):
        """A customer can access their own order status."""
        session = self.client.session
        session['customer_id'] = self.customer_a.pk
        session.save()
        url = reverse('order_status', kwargs={'pk': self.order_a.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_customer_access_other_customer_order_fails(self):
        """A customer cannot access another customer's order status."""
        session = self.client.session
        session['customer_id'] = self.customer_b.pk
        session.save()
        url = reverse('order_status', kwargs={'pk': self.order_a.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_customer_access_guest_order_fails(self):
        """A logged-in customer cannot access a guest order status."""
        session = self.client.session
        session['customer_id'] = self.customer_b.pk
        session.save()
        url = reverse('order_status', kwargs={'pk': self.order_guest.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


