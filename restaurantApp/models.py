from django.db import models

class PreferenceGroup(models.Model):
    TYPE_CHOICES = [
        ("Independent", "Independent"),
        ("Dependent", "Dependent"),
    ]
    OPTION_CHOICES = [
        ("optional", "Optional"),
        ("required", "Required"),
        ("multiple", "Can be selected more than once"),
        ("N/A", "N/A"),
    ]
    PRICING_CHOICES = [
        ("No Charge", "No Charge"),
        ("Group Pricing", "Group Pricing"),
        ("Individual Pricing", "Individual Pricing"),
    ]

    name = models.CharField(max_length=100, unique=True)
    group_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="Independent")
    group_option = models.CharField(max_length=20, choices=OPTION_CHOICES, default="optional")

    min_pref = models.PositiveIntegerField(default=1, null=True, blank=True)
    max_pref = models.PositiveIntegerField(default=10, null=True, blank=True)
    pricing_method = models.CharField(max_length=30, choices=PRICING_CHOICES, default="No Charge")
    group_price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    multiple_selection_limit = models.BooleanField(default=False)
    parent_name = models.CharField(max_length=100, default="Add Column")
    child_name = models.CharField(max_length=100, default="Add Row")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def get_preferences_count(self):
        return self.preferences.count()
    
    def get_ingredients_count(self):
        return self.ingredients.count()
    
    def get_columns_count(self):
        return self.columns.count()


class Preference(models.Model):
    group = models.ForeignKey(PreferenceGroup, on_delete=models.CASCADE, related_name="preferences")
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    order_index = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order_index']

    def __str__(self):
        return f"{self.name} ({self.group.name})"


class DependentIngredient(models.Model):
    group = models.ForeignKey(PreferenceGroup, on_delete=models.CASCADE, related_name="ingredients")
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    order_index = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order_index']

    def __str__(self):
        return f"{self.name} ({self.group.name})"


class DependentColumn(models.Model):
    group = models.ForeignKey(PreferenceGroup, on_delete=models.CASCADE, related_name="columns")
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    order_index = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order_index']

    def __str__(self):
        return f"{self.name} ({self.group.name})"


class DependentRule(models.Model):
    ingredient = models.ForeignKey(DependentIngredient, on_delete=models.CASCADE, related_name="rules")
    column = models.ForeignKey(DependentColumn, on_delete=models.CASCADE, related_name="rules")
    show = models.BooleanField(default=False)
    default = models.BooleanField(default=False)
    allow_more = models.BooleanField(default=False)
    required = models.BooleanField(default=False)

    class Meta:
        unique_together = ('ingredient', 'column')

    def __str__(self):
        return f"Rule({self.ingredient.name} x {self.column.name})"