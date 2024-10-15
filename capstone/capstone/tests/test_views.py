import unittest
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Post, Pub
import json

class TestViews(TestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.client = Client()
        self.client.login(username='testuser', password='testpassword')

        # Create a test pub
        self.pub = Pub.objects.create(
            name='Test Pub',
            address='123 Test Street',
            latitude=51.5074,
            longitude=-0.1278,
            inventory_stars='3',
            url='https://example.com',
            description='Test description',
            open=True,
            listed=True
        )

    def test_privacy_policy_view(self):
        response = self.client.get(reverse('privacy_policy'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'account/privacypolicy.html')

    def test_contact_view(self):
        response = self.client.get(reverse('contact'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'contact.html')

    def test_landing_view_authenticated(self):
        response = self.client.get(reverse('landing'))
        self.assertRedirects(response, reverse('index'))

    def test_landing_view_unauthenticated(self):
        self.client.logout()
        response = self.client.get(reverse('landing'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'landing.html')

    def test_index_view_authenticated(self):
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'index.html')
        self.assertIn('pubs', response.context)

    def test_index_view_unauthenticated(self):
        self.client.logout()
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'index.html')
        self.assertIsNone(response.context.get('pubs'))

    def test_admin_refresh_emails_view(self):
        self.user.is_staff = True
        self.user.save()
        response = self.client.get(reverse('admin_refresh_emails'))
        self.assertRedirects(response, reverse('privacy_policy'))

    def test_pubs_api_view(self):
        # Correct the reverse lookup to match the URL name 'pubs_api'
        response = self.client.get(reverse('pubs_api'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('pubs', response.json())

    def test_save_visit_view(self):
        data = {
            'pub_id': self.pub.id,
            'content': 'Test content',
            'date_visited': '2024-10-10'
        }
        # Ensure to correctly reverse the 'save_visit' URL
        response = self.client.post(reverse('save_visit'), data=json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Post.objects.filter(pub=self.pub, owner=self.user).count(), 1)

    def test_delete_visit_view(self):
        post = Post.objects.create(content='Test content', owner=self.user, pub=self.pub)
        data = {'pub_id': self.pub.id}
        # Ensure to correctly reverse the 'delete_visit' URL
        response = self.client.post(reverse('delete_visit'), data=json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Post.objects.filter(pub=self.pub, owner=self.user).count(), 0)

if __name__ == '__main__':
    unittest.main()
