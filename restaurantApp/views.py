from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
import json
from django.db import transaction
from django.contrib import messages
from .models import (
    PreferenceGroup,
    Preference,
    DependentIngredient,
    DependentColumn,
    DependentRule,
)


def preference_group_list(request):
    """List all preference groups with optimized queries"""
    groups = PreferenceGroup.objects.all().order_by("-created_at").prefetch_related(
        'preferences',
        'ingredients',
        'columns',
        'ingredients__rules__column'
    )
    return render(request, "group_list.html", {"groups": groups})


def preference_group_create(request):
    if request.method == "GET":
        return render(request, "new_group.html")

    if request.method != "POST":
        return HttpResponseBadRequest("Invalid method")

    name = request.POST.get("name")
    group_type = request.POST.get("type")
    group_option = request.POST.get("group_option")
    pricing_method = request.POST.get("pricingMethod")
    min_pref = request.POST.get("minPref") or 1
    max_pref = request.POST.get("maxPref") or 10
    group_price = request.POST.get("groupPrice") or 0

    if not name:
        messages.error(request, "Group name is required")
        return render(request, "new_group.html")

    try:
        with transaction.atomic():
            group = PreferenceGroup.objects.create(
                name=name,
                group_type=group_type,
                group_option=group_option,
                pricing_method=pricing_method,
                min_pref=min_pref,
                max_pref=max_pref,
                group_price=group_price,
            )

            # --- Independent Group ---
            if group_type == "Independent":
                prefs = request.POST.getlist("preferences[]", [])
                prices = request.POST.getlist("prices[]", [])
                
                if not prefs:
                    messages.error(request, "At least one preference is required for Independent groups")
                    group.delete()  # Delete the group since no preferences were added
                    return render(request, "new_group.html")
                
                for pref_name, price in zip(prefs, prices):
                    if pref_name.strip():
                        try:
                            price_value = float(price) if price else 0.0
                            Preference.objects.create(
                                group=group, 
                                name=pref_name.strip(), 
                                price=price_value
                            )
                        except (ValueError, TypeError):
                            Preference.objects.create(
                                group=group, 
                                name=pref_name.strip(), 
                                price=0.0
                            )

            # --- Dependent Group ---
            elif group_type == "Dependent":
                ingredients = request.POST.getlist("ingredients[]", [])
                ingredients_price = request.POST.getlist("ingredients_price[]", [])
                columns = request.POST.getlist("columns[]", [])
                columns_price = request.POST.getlist("columns_price[]", [])

                # Validate that we have at least one ingredient and one column
                if not ingredients or not columns:
                    messages.error(request, "Dependent groups require at least one ingredient and one column")
                    group.delete()
                    return render(request, "new_group.html")

                ing_objs = []
                for ing_name, price in zip(ingredients, ingredients_price):
                    if ing_name.strip():
                        try:
                            price_value = float(price) if price else 0.0
                            ing_obj = DependentIngredient.objects.create(
                                group=group, 
                                name=ing_name.strip(), 
                                price=price_value
                            )
                            ing_objs.append(ing_obj)
                        except (ValueError, TypeError):
                            ing_obj = DependentIngredient.objects.create(
                                group=group, 
                                name=ing_name.strip(), 
                                price=0.0
                            )
                            ing_objs.append(ing_obj)

                col_objs = []
                for col_name, price in zip(columns, columns_price):
                    if col_name.strip():
                        try:
                            price_value = float(price) if price else 0.0
                            col_obj = DependentColumn.objects.create(
                                group=group, 
                                name=col_name.strip(), 
                                price=price_value
                            )
                            col_objs.append(col_obj)
                        except (ValueError, TypeError):
                            col_obj = DependentColumn.objects.create(
                                group=group, 
                                name=col_name.strip(), 
                                price=0.0
                            )
                            col_objs.append(col_obj)

                # --- Handle rules (checkbox matrix) ---
                rules_json = request.POST.get("rules_json")
                if rules_json:
                    try:
                        rules_data = json.loads(rules_json)
                        created_rules_count = 0
                        
                        for rule in rules_data:
                            ing_idx = rule.get("ingredient_index")
                            col_idx = rule.get("column_index")
                            show = rule.get("show", False)
                            default = rule.get("default", False)
                            required = rule.get("required", False)

                            if (ing_idx is not None and col_idx is not None and 
                                0 <= ing_idx < len(ing_objs) and 0 <= col_idx < len(col_objs)):
                                
                                DependentRule.objects.create(
                                    ingredient=ing_objs[ing_idx],
                                    column=col_objs[col_idx],
                                    show=bool(show),
                                    default=bool(default),
                                    required=bool(required),
                                )
                                created_rules_count += 1
                        
                        # If no rules were created, create default rules (all unchecked)
                        if created_rules_count == 0:
                            for ing_obj in ing_objs:
                                for col_obj in col_objs:
                                    DependentRule.objects.create(
                                        ingredient=ing_obj,
                                        column=col_obj,
                                        show=False,
                                        default=False,
                                        required=False,
                                    )
                    
                    except json.JSONDecodeError:
                        # If rules JSON is invalid, create default rules
                        for ing_obj in ing_objs:
                            for col_obj in col_objs:
                                DependentRule.objects.create(
                                    ingredient=ing_obj,
                                    column=col_obj,
                                    show=False,
                                    default=False,
                                    required=False,
                                )
                else:
                    # If no rules JSON provided, create default rules
                    for ing_obj in ing_objs:
                        for col_obj in col_objs:
                            DependentRule.objects.create(
                                ingredient=ing_obj,
                                column=col_obj,
                                show=False,
                                default=False,
                                required=False,
                            )

        messages.success(request, f"Preference group '{name}' created successfully!")
        return redirect("group_list")

    except Exception as e:
        messages.error(request, f"Error creating preference group: {str(e)}")
        return render(request, "new_group.html")


def preference_group_edit(request, group_id):
    """Edit an existing preference group"""
    group = get_object_or_404(PreferenceGroup, id=group_id)
    
    if request.method == "GET":
        # Preload existing data for editing
        context = {
            'group': group,
        }
        return render(request, "edit_group.html", context)
    
    # Handle POST request for updates (similar to create but with updates instead of creates)
    # Implementation would be similar to create but with update logic


def preference_group_delete(request, group_id):
    """Delete a preference group"""
    group = get_object_or_404(PreferenceGroup, id=group_id)
    
    if request.method == "POST":
        group_name = group.name
        group.delete()
        messages.success(request, f"Preference group '{group_name}' deleted successfully!")
        return redirect("group_list")
    
    return redirect("group_list")