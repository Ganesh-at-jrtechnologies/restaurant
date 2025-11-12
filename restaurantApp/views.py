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
    group_option = "N/A" if request.POST.get("type").strip() == "Dependent" else request.POST.get("group_option", "").strip()
    print(f"Group option: {group_option}++++++++++++++")
    multiple_selection = request.POST.get("multiple_selection")
    pricing_method = request.POST.get("pricingMethod")
    min_pref = request.POST.get("minPref") or 1
    max_pref = request.POST.get("maxPref") or 10
    group_price = request.POST.get("groupPrice") or 0
    row_name = request.POST.get("rowName") or ""
    column_name = request.POST.get("columnName") or ""


    if not name:
        messages.error(request, "Group name is required")
        return render(request, "new_group.html")

    try:
        with transaction.atomic():
            group = PreferenceGroup.objects.create(
                name=name,
                group_type=group_type,
                group_option=group_option,
                multiple_selection_limit=bool(multiple_selection),
                child_name=row_name,
                parent_name=column_name,
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
                    group.delete()
                    return render(request, "new_group.html")
                
                for order_index, (pref_name, price) in enumerate(zip(prefs, prices)):
                    if pref_name.strip():
                        try:
                            price_value = float(price) if price else 0.0
                            Preference.objects.create(
                                group=group, 
                                name=pref_name.strip(), 
                                price=price_value,
                                order_index=order_index
                            )
                        except (ValueError, TypeError):
                            Preference.objects.create(
                                group=group, 
                                name=pref_name.strip(), 
                                price=0.0,
                                order_index=order_index
                            )

            # --- Dependent Group ---
            elif group_type == "Dependent":
                ingredients = request.POST.getlist("ingredients[]", [])
                ingredients_price = request.POST.getlist("ingredients_price[]", [])
                columns = request.POST.getlist("columns[]", [])
                columns_price = request.POST.getlist("columns_price[]", [])

                if not ingredients or not columns:
                    messages.error(request, "Dependent groups require at least one ingredient and one column")
                    group.delete()
                    return render(request, "new_group.html")

                # Create ingredients with order index
                ing_objs = []
                for order_index, (ing_name, price) in enumerate(zip(ingredients, ingredients_price)):
                    if ing_name.strip():
                        try:
                            price_value = float(price) if price else 0.0
                            ing_obj = DependentIngredient.objects.create(
                                group=group, 
                                name=ing_name.strip(), 
                                price=price_value,
                                order_index=order_index
                            )
                            ing_objs.append(ing_obj)
                        except (ValueError, TypeError):
                            ing_obj = DependentIngredient.objects.create(
                                group=group, 
                                name=ing_name.strip(), 
                                price=0.0,
                                order_index=order_index
                            )
                            ing_objs.append(ing_obj)

                # Create columns with order index
                col_objs = []
                for order_index, (col_name, price) in enumerate(zip(columns, columns_price)):
                    if col_name.strip():
                        try:
                            price_value = float(price) if price else 0.0
                            col_obj = DependentColumn.objects.create(
                                group=group, 
                                name=col_name.strip(), 
                                price=price_value,
                                order_index=order_index
                            )
                            col_objs.append(col_obj)
                        except (ValueError, TypeError):
                            col_obj = DependentColumn.objects.create(
                                group=group, 
                                name=col_name.strip(), 
                                price=0.0,
                                order_index=order_index
                            )
                            col_objs.append(col_obj)

                # Handle rules
                rules_json = request.POST.get("rules_json")
                if rules_json:
                    try:
                        rules_data = json.loads(rules_json)
                        
                        for rule in rules_data:
                            ing_idx = rule.get("ingredient_index")
                            col_idx = rule.get("column_index")
                            show = rule.get("show", False)
                            default = rule.get("default", False)
                            required = rule.get("required", False)
                            allow_more = rule.get("allow_more", False)

                            if (ing_idx is not None and col_idx is not None and 
                                0 <= ing_idx < len(ing_objs) and 0 <= col_idx < len(col_objs)):
                                
                                DependentRule.objects.create(
                                    ingredient=ing_objs[ing_idx],
                                    column=col_objs[col_idx],
                                    show=bool(show),
                                    default=bool(default),
                                    required=bool(required),
                                    allow_more=bool(allow_more),
                                )
                        
                        # If no rules were created, create default rules
                        if len(rules_data) == 0:
                            for ing_obj in ing_objs:
                                for col_obj in col_objs:
                                    DependentRule.objects.create(
                                        ingredient=ing_obj,
                                        column=col_obj,
                                        show=False,
                                        default=False,
                                        required=False,
                                        allow_more=False,
                                    )
                    
                    except json.JSONDecodeError:
                        for ing_obj in ing_objs:
                            for col_obj in col_objs:
                                DependentRule.objects.create(
                                    ingredient=ing_obj,
                                    column=col_obj,
                                    show=False,
                                    default=False,
                                    required=False,
                                    allow_more=False,
                                )
                else:
                    for ing_obj in ing_objs:
                        for col_obj in col_objs:
                            DependentRule.objects.create(
                                ingredient=ing_obj,
                                column=col_obj,
                                show=False,
                                default=False,
                                required=False,
                                allow_more=False,
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
        context = {
            'group': group,
        }
        
        # Load data with proper ordering
        preferences = group.preferences.all().order_by('order_index')
        context['preferences'] = preferences

        ingredients = group.ingredients.all().order_by('order_index')
        columns = group.columns.all().order_by('order_index')
        
        # Prefetch rules for efficient querying
        ingredients_with_rules = ingredients.prefetch_related('rules__column')
        
        # Create rules matrix
        rules_matrix = []
        for ingredient in ingredients_with_rules:
            ingredient_data = {
                'ingredient_name': ingredient.name,
                'ingredient_id': ingredient.id,
                'ingredient_price': ingredient.price,
                'rules': []
            }
            for column in columns:
                rule = next((r for r in ingredient.rules.all() if r.column_id == column.id), None)
                ingredient_data['rules'].append({
                    'ingredient_id': ingredient.id,
                    'column_id': column.id,
                    'column_name': column.name,
                    'price': column.price,
                    'show': rule.show if rule else False,
                    'default': rule.default if rule else False,
                    'required': rule.required if rule else False,
                    'allow_more': rule.allow_more if rule else False,
                })
            rules_matrix.append(ingredient_data)
        
        context.update({
            'ingredients': ingredients,
            'columns': columns,
            'rules_matrix': rules_matrix,
        })
            
        return render(request, "edit_group.html", context)
    
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid method")
    
    print("POST Data:", request.POST.dict(),"-------------------")

    name = request.POST.get("name")
    group_type = request.POST.get("type")
    group_option = request.POST.get("group_option")
    multiple_selection = request.POST.get("multiple_selection")
    pricing_method = request.POST.get("pricingMethod")
    min_pref = request.POST.get("minPref") or 1
    max_pref = request.POST.get("maxPref") or 10
    group_price = request.POST.get("groupPrice") or 0

    if not name:
        messages.error(request, "Group name is required")
        return redirect("group_edit", group_id=group_id)

    try:
        with transaction.atomic():
            # Update the main group
            group.name = name
            group.group_type = group_type
            group.group_option = group_option
            group.multiple_selection_limit = bool(multiple_selection)
            group.pricing_method = pricing_method
            group.min_pref = min_pref
            group.max_pref = max_pref
            group.group_price = group_price
            group.save()

            # --- Independent Group ---
            if group_type == "Independent":
                group.preferences.all().delete()
                
                prefs = request.POST.getlist("preferences[]", [])
                prices = request.POST.getlist("prices[]", [])
                
                if not prefs:
                    messages.error(request, "At least one preference is required for Independent groups")
                    return redirect("group_edit", group_id=group_id)
                
                for order_index, (pref_name, price) in enumerate(zip(prefs, prices)):
                    if pref_name.strip():
                        try:
                            price_value = float(price) if price else 0.0
                            Preference.objects.create(
                                group=group, 
                                name=pref_name.strip(), 
                                price=price_value,
                                order_index=order_index
                            )
                        except (ValueError, TypeError):
                            Preference.objects.create(
                                group=group, 
                                name=pref_name.strip(), 
                                price=0.0,
                                order_index=order_index
                            )

            # --- Dependent Group ---
            elif group_type == "Dependent":
                ingredients = request.POST.getlist("ingredients[]", [])
                ingredients_price = request.POST.getlist("ingredients_price[]", [])
                columns = request.POST.getlist("columns[]", [])
                columns_price = request.POST.getlist("columns_price[]", [])

                print(f"Received ingredients: {ingredients}")
                print(f"Received ingredients_price: {ingredients_price}")
                print(f"Received columns: {columns}")
                print(f"Received columns_price: {columns_price}")

                if not ingredients or not columns:
                    messages.error(request, "Dependent groups require at least one ingredient and one column")
                    return redirect("group_edit", group_id=group_id)

                # Clear existing data
                group.ingredients.all().delete()
                group.columns.all().delete()
                
                # Create new ingredients with order index
                ing_objs = []
                for order_index, (ing_name, price) in enumerate(zip(ingredients, ingredients_price)):
                    if ing_name.strip():
                        try:
                            price_value = float(price) if price else 0.0
                            ing_obj = DependentIngredient.objects.create(
                                group=group, 
                                name=ing_name.strip(), 
                                price=price_value,
                                order_index=order_index
                            )
                            ing_objs.append(ing_obj)
                        except (ValueError, TypeError):
                            ing_obj = DependentIngredient.objects.create(
                                group=group, 
                                name=ing_name.strip(), 
                                price=0.0,
                                order_index=order_index
                            )
                            ing_objs.append(ing_obj)

                # Create new columns with order index
                col_objs = []
                for order_index, (col_name, price) in enumerate(zip(columns, columns_price)):
                    if col_name.strip():
                        try:
                            price_value = float(price) if price else 0.0
                            col_obj = DependentColumn.objects.create(
                                group=group, 
                                name=col_name.strip(), 
                                price=price_value,
                                order_index=order_index
                            )
                            col_objs.append(col_obj)
                        except (ValueError, TypeError):
                            col_obj = DependentColumn.objects.create(
                                group=group, 
                                name=col_name.strip(), 
                                price=0.0,
                                order_index=order_index
                            )
                            col_objs.append(col_obj)

                # Handle rules
                rules_json = request.POST.get("rules_json")
                print(f"Received rules_json: {rules_json}")
                
                if rules_json:
                    try:
                        rules_data = json.loads(rules_json)
                        
                        for rule in rules_data:
                            ing_idx = rule.get("ingredient_index")
                            col_idx = rule.get("column_index")
                            show = rule.get("show", False)
                            default = rule.get("default", False)
                            required = rule.get("required", False)
                            allow_more = rule.get("allow_more", False)

                            print(f"Processing rule: ing_idx={ing_idx}, col_idx={col_idx}, show={show}, default={default}, required={required}, allow_more={allow_more}")

                            if (ing_idx is not None and col_idx is not None and 
                                0 <= ing_idx < len(ing_objs) and 0 <= col_idx < len(col_objs)):
                                
                                DependentRule.objects.create(
                                    ingredient=ing_objs[ing_idx],
                                    column=col_objs[col_idx],
                                    show=bool(show),
                                    default=bool(default),
                                    required=bool(required),
                                    allow_more=bool(allow_more)
                                )
                        
                        # If no rules were created, create default rules
                        if len(rules_data) == 0:
                            for ing_obj in ing_objs:
                                for col_obj in col_objs:
                                    DependentRule.objects.create(
                                        ingredient=ing_obj,
                                        column=col_obj,
                                        show=False,
                                        default=False,
                                        required=False,
                                        allow_more=False,
                                    )
                    
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error: {e}")
                        for ing_obj in ing_objs:
                            for col_obj in col_objs:
                                DependentRule.objects.create(
                                    ingredient=ing_obj,
                                    column=col_obj,
                                    show=False,
                                    default=False,
                                    required=False,
                                    allow_more=False,
                                )
                else:
                    print("No rules JSON provided, creating default rules")
                    for ing_obj in ing_objs:
                        for col_obj in col_objs:
                            DependentRule.objects.create(
                                ingredient=ing_obj,
                                column=col_obj,
                                show=False,
                                default=False,
                                required=False,
                                allow_more=False,
                            )

        messages.success(request, f"Preference group '{name}' updated successfully!")
        return redirect("group_edit")

    except Exception as e:
        messages.error(request, f"Error updating preference group: {str(e)}")
        import traceback
        print(f"Error: {str(e)}")
        print(traceback.format_exc())
        return redirect("group_edit", group_id=group_id)


def preference_group_delete(request, group_id):
    """Delete a preference group"""
    group = get_object_or_404(PreferenceGroup, id=group_id)
    
    if request.method == "POST":
        group_name = group.name
        group.delete()
        messages.success(request, f"Preference group '{group_name}' deleted successfully!")
        return redirect("group_list")
    
    return redirect("group_list")