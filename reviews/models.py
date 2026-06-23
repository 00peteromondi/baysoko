from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()

class Review(models.Model):
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_given')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_received')
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField()
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('reviewer', 'seller')

    def __str__(self):
        return f"{self.rating} stars by {self.reviewer.username} for {self.seller.username}"