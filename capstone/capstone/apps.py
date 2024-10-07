from django.apps import AppConfig

class CapstoneConfig(AppConfig):
    name = 'capstone'  # Replace with your app name

    def ready(self):
        import capstone.signals  # Import the signals module to ensure they are registered
