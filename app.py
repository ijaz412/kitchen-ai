import json
import os
import re
from typing import Any, Dict, List

import requests
import streamlit as st


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Chef AI",
    page_icon="🍳",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# GROQ API CONFIGURATION
# ============================================================

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

GROQ_MODEL = "openai/gpt-oss-20b"


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    /* Main application */
    .stApp {
        background-color: #fffaf4;
    }

    /* Main content */
    .block-container {
        max-width: 1200px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    /* Main title */
    .main-title {
        font-size: 48px;
        font-weight: 800;
        color: #3b2418;
        margin-bottom: 5px;
    }

    .main-subtitle {
        font-size: 18px;
        color: #806b5c;
        margin-bottom: 30px;
    }

    /* Cards */
    .recipe-card {
        background: white;
        border: 1px solid #eadfd5;
        border-radius: 18px;
        padding: 25px;
        margin-bottom: 20px;
        box-shadow: 0 4px 18px rgba(60, 40, 25, 0.06);
    }

    /* Recipe title */
    .recipe-title {
        font-size: 36px;
        font-weight: 800;
        color: #3b2418;
        margin-bottom: 10px;
    }

    /* Section titles */
    .section-title {
        font-size: 25px;
        font-weight: 750;
        color: #4a2e20;
        margin-top: 25px;
        margin-bottom: 12px;
    }

    /* Ingredient */
    .ingredient-row {
        background: #fffdf9;
        border-bottom: 1px solid #eee4db;
        padding: 11px 5px;
    }

    /* Instruction step */
    .step-box {
        background: #fff;
        border: 1px solid #eee4db;
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 12px;
    }

    .step-number {
        font-weight: 800;
        color: #d3543f;
    }

    /* Suggestion card */
    .suggestion-card {
        background: white;
        border: 1px solid #eadfd5;
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 15px;
    }

    /* Info boxes */
    .info-box {
        background: #fff3e7;
        border-radius: 12px;
        padding: 15px;
        margin: 10px 0;
    }

    /* Footer */
    .app-footer {
        text-align: center;
        color: #927e70;
        font-size: 14px;
        padding: 30px 0 10px 0;
    }

    /* Mobile */
    @media (max-width: 768px) {

        .main-title {
            font-size: 36px;
        }

        .main-subtitle {
            font-size: 16px;
        }

        .recipe-title {
            font-size: 28px;
        }

        .section-title {
            font-size: 22px;
        }
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SESSION STATE
# ============================================================

if "page" not in st.session_state:
    st.session_state.page = "Home"

if "recipe" not in st.session_state:
    st.session_state.recipe = None

if "suggestions" not in st.session_state:
    st.session_state.suggestions = []

if "favorites" not in st.session_state:
    st.session_state.favorites = []


# ============================================================
# GET GROQ API KEY
# ============================================================

def get_api_key() -> str:
    """
    Get the Groq API key from Streamlit Secrets.

    Expected Streamlit Secret:

    GROQ_API_KEY = "gsk_your_key_here"
    """

    try:
        secret_key = st.secrets.get("GROQ_API_KEY", "")
    except Exception:
        secret_key = ""

    if secret_key:
        return str(secret_key).strip()

    environment_key = os.getenv("GROQ_API_KEY", "")

    return environment_key.strip()


# ============================================================
# CALL GROQ
# ============================================================

def call_groq(prompt: str) -> str:

    api_key = get_api_key()

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is missing. "
            "Please add your gsk_... Groq API key "
            "to Streamlit Secrets."
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are Chef AI, an expert cooking assistant. "
                    "Create practical, accurate, delicious and "
                    "beginner-friendly recipes. "
                    "When JSON is requested, return valid JSON only."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.4,
    }

    try:

        response = requests.post(
            GROQ_API_URL,
            headers=headers,
            json=payload,
            timeout=90,
        )

    except requests.RequestException as error:

        raise RuntimeError(
            f"Could not connect to Groq API: {error}"
        )

    if response.status_code != 200:

        try:
            error_data = response.json()

            if isinstance(error_data, dict):

                if "error" in error_data:
                    error_message = error_data["error"]

                else:
                    error_message = error_data

            else:
                error_message = error_data

        except Exception:

            error_message = response.text

        raise RuntimeError(
            f"Groq API error {response.status_code}: "
            f"{error_message}"
        )

    try:

        data = response.json()

        content = (
            data["choices"][0]["message"]["content"]
        )

        if not content:
            raise ValueError(
                "Empty response from Groq."
            )

        return content

    except Exception as error:

        raise RuntimeError(
            f"Unexpected Groq response: {error}"
        )


# ============================================================
# EXTRACT JSON
# ============================================================

def extract_json(text: str) -> Any:

    text = text.strip()

    # Remove markdown code fences
    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"^```\s*",
        "",
        text,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    # Try direct JSON
    try:

        return json.loads(text)

    except json.JSONDecodeError:
        pass

    # Try JSON object
    object_start = text.find("{")
    object_end = text.rfind("}")

    if (
        object_start != -1
        and object_end != -1
        and object_end > object_start
    ):

        candidate = text[
            object_start:object_end + 1
        ]

        try:

            return json.loads(candidate)

        except json.JSONDecodeError:
            pass

    # Try JSON array
    array_start = text.find("[")
    array_end = text.rfind("]")

    if (
        array_start != -1
        and array_end != -1
        and array_end > array_start
    ):

        candidate = text[
            array_start:array_end + 1
        ]

        try:

            return json.loads(candidate)

        except json.JSONDecodeError:
            pass

    raise ValueError(
        "The AI returned invalid JSON."
    )


# ============================================================
# GENERATE COMPLETE RECIPE
# ============================================================

def generate_recipe(
    dish: str,
    servings: int,
) -> Dict[str, Any]:

    prompt = f"""
Create a complete recipe for:

Dish: {dish}

Servings: {servings}

Return ONLY valid JSON.

Use exactly this structure:

{{
    "name": "Recipe name",
    "description": "Short appetizing description",
    "servings": {servings},
    "prep_time": "15 minutes",
    "cook_time": "30 minutes",
    "total_time": "45 minutes",
    "difficulty": "Easy",
    "ingredients": [
        {{
            "item": "ingredient name",
            "quantity": "quantity",
            "notes": "optional preparation note"
        }}
    ],
    "steps": [
        "First cooking step",
        "Second cooking step",
        "Third cooking step"
    ],
    "tips": [
        "Useful cooking tip"
    ],
    "substitutions": [
        {{
            "original": "ingredient",
            "replacement": "replacement"
        }}
    ],
    "serving_suggestions": [
        "Serving suggestion"
    ],
    "food_safety": [
        "Food safety instruction"
    ]
}}

Rules:

1. Make the recipe for exactly {servings} servings.
2. Use realistic ingredient quantities.
3. Give clear beginner-friendly instructions.
4. Include preparation time.
5. Include cooking time.
6. Include total time.
7. Include difficulty.
8. Include useful cooking tips.
9. Include practical ingredient substitutions.
10. Include serving suggestions.
11. Include food safety advice.
12. Do not use markdown.
13. Return JSON only.
"""

    response = call_groq(prompt)

    data = extract_json(response)

    if not isinstance(data, dict):

        raise ValueError(
            "Recipe response was not a JSON object."
        )

    return data


# ============================================================
# FIND RECIPES FROM INGREDIENTS
# ============================================================

def find_recipes_from_ingredients(
    ingredients: List[str],
    servings: int,
) -> List[Dict[str, Any]]:

    ingredient_text = ", ".join(ingredients)

    prompt = f"""
The user has these ingredients:

{ingredient_text}

They want to cook for {servings} people.

Suggest 6 realistic dishes they can make.

Prioritize recipes that use the ingredients
they already have.

Return ONLY valid JSON using exactly:

{{
    "recipes": [
        {{
            "name": "Dish name",
            "description": "Short description",
            "match_percentage": 85,
            "uses": [
                "ingredient already available"
            ],
            "missing": [
                "ingredient they may need"
            ]
        }}
    ]
}}

Rules:

1. Prioritize existing ingredients.
2. Do not suggest unrealistic combinations.
3. Give approximately 6 recipes.
4. Show ingredients the user already has.
5. Show ingredients they are missing.
6. Match percentage should represent how well
   their ingredients fit the recipe.
7. Keep descriptions short.
8. Do not use markdown.
9. Return JSON only.
"""

    response = call_groq(prompt)

    data = extract_json(response)

    if isinstance(data, dict):

        recipes = data.get(
            "recipes",
            [],
        )

    elif isinstance(data, list):

        recipes = data

    else:

        recipes = []

    return recipes


# ============================================================
# RENDER RECIPE
# IMPORTANT:
# This function is defined BEFORE it is called.
# This fixes the NameError from your screenshot.
# ============================================================

def render_recipe(
    recipe: Dict[str, Any]
):

    if not recipe:
        return

    st.markdown("---")

    # --------------------------------------------------------
    # Recipe title
    # --------------------------------------------------------

    recipe_name = recipe.get(
        "name",
        "Recipe",
    )

    st.markdown(
        f"""
        <div class="recipe-title">
            {recipe_name}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # Description
    # --------------------------------------------------------

    description = recipe.get(
        "description",
        "",
    )

    if description:

        st.write(description)

    # --------------------------------------------------------
    # Recipe information
    # --------------------------------------------------------

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "Servings",
            recipe.get(
                "servings",
                "-",
            ),
        )

    with col2:

        st.metric(
            "Prep Time",
            recipe.get(
                "prep_time",
                "-",
            ),
        )

    with col3:

        st.metric(
            "Cook Time",
            recipe.get(
                "cook_time",
                "-",
            ),
        )

    with col4:

        st.metric(
            "Difficulty",
            recipe.get(
                "difficulty",
                "-",
            ),
        )

    # --------------------------------------------------------
    # Favorite
    # --------------------------------------------------------

    is_favorite = any(
        favorite.get("name") == recipe_name
        for favorite in st.session_state.favorites
    )

    if is_favorite:

        if st.button(
            "💔 Remove from Favorites",
            use_container_width=True,
        ):

            st.session_state.favorites = [
                favorite
                for favorite
                in st.session_state.favorites
                if favorite.get("name") != recipe_name
            ]

            st.success(
                "Recipe removed from favorites."
            )

            st.rerun()

    else:

        if st.button(
            "❤️ Save to Favorites",
            use_container_width=True,
        ):

            st.session_state.favorites.append(
                recipe
            )

            st.success(
                "Recipe saved to favorites!"
            )

    # --------------------------------------------------------
    # Ingredients
    # --------------------------------------------------------

    st.markdown(
        '<div class="section-title">'
        '🧺 Ingredients'
        '</div>',
        unsafe_allow_html=True,
    )

    ingredients = recipe.get(
        "ingredients",
        [],
    )

    if not ingredients:

        st.write(
            "No ingredients were returned."
        )

    for ingredient in ingredients:

        if isinstance(
            ingredient,
            dict,
        ):

            item = ingredient.get(
                "item",
                "",
            )

            quantity = ingredient.get(
                "quantity",
                "",
            )

            notes = ingredient.get(
                "notes",
                "",
            )

            ingredient_text = (
                f"<strong>{quantity}</strong> "
                f"{item}"
            )

            if notes:

                ingredient_text += (
                    f" — {notes}"
                )

            st.markdown(
                f"""
                <div class="ingredient-row">
                    {ingredient_text}
                </div>
                """,
                unsafe_allow_html=True,
            )

        else:

            st.markdown(
                f"""
                <div class="ingredient-row">
                    {ingredient}
                </div>
                """,
                unsafe_allow_html=True,
            )

    # --------------------------------------------------------
    # Instructions
    # --------------------------------------------------------

    st.markdown(
        '<div class="section-title">'
        '👨‍🍳 Instructions'
        '</div>',
        unsafe_allow_html=True,
    )

    steps = recipe.get(
        "steps",
        [],
    )

    if not steps:

        st.write(
            "No instructions were returned."
        )

    for index, step in enumerate(
        steps,
        start=1,
    ):

        st.markdown(
            f"""
            <div class="step-box">
                <span class="step-number">
                    Step {index}
                </span>
                <br>
                {step}
            </div>
            """,
            unsafe_allow_html=True,
        )

    # --------------------------------------------------------
    # Tips
    # --------------------------------------------------------

    tips = recipe.get(
        "tips",
        [],
    )

    if tips:

        st.markdown(
            '<div class="section-title">'
            '💡 Cooking Tips'
            '</div>',
            unsafe_allow_html=True,
        )

        for tip in tips:

            st.write(
                f"• {tip}"
            )

    # --------------------------------------------------------
    # Substitutions
    # --------------------------------------------------------

    substitutions = recipe.get(
        "substitutions",
        [],
    )

    if substitutions:

        st.markdown(
            '<div class="section-title">'
            '🔄 Substitutions'
            '</div>',
            unsafe_allow_html=True,
        )

        for substitution in substitutions:

            if isinstance(
                substitution,
                dict,
            ):

                original = substitution.get(
                    "original",
                    "",
                )

                replacement = substitution.get(
                    "replacement",
                    "",
                )

                st.write(
                    f"**{original} → {replacement}**"
                )

            else:

                st.write(
                    f"• {substitution}"
                )

    # --------------------------------------------------------
    # Serving suggestions
    # --------------------------------------------------------

    serving_suggestions = recipe.get(
        "serving_suggestions",
        [],
    )

    if serving_suggestions:

        st.markdown(
            '<div class="section-title">'
            '🍽️ Serving Suggestions'
            '</div>',
            unsafe_allow_html=True,
        )

        for suggestion in serving_suggestions:

            st.write(
                f"• {suggestion}"
            )

    # --------------------------------------------------------
    # Food safety
    # --------------------------------------------------------

    food_safety = recipe.get(
        "food_safety",
        [],
    )

    if food_safety:

        st.markdown(
            '<div class="section-title">'
            '🛡️ Food Safety'
            '</div>',
            unsafe_allow_html=True,
        )

        for safety in food_safety:

            st.write(
                f"• {safety}"
            )

    # --------------------------------------------------------
    # Print/share
    # --------------------------------------------------------

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:

        st.info(
            "🖨️ To print this recipe, "
            "use your browser's Print option."
        )

    with col2:

        st.info(
            "🔗 You can share this page "
            "using your browser's share/copy link option."
        )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        "## 🍳 Chef AI"
    )

    st.caption(
        "Your smart kitchen assistant"
    )

    st.divider()

    selected_page = st.radio(
        "Menu",
        [
            "Home",
            "Find a Recipe",
            "Use My Ingredients",
            "Favorites",
        ],
        index=[
            "Home",
            "Find a Recipe",
            "Use My Ingredients",
            "Favorites",
        ].index(
            st.session_state.page
        ),
    )

    st.session_state.page = selected_page

    st.divider()

    st.caption(
        "Powered by Groq API"
    )


# ============================================================
# MAIN HEADER
# ============================================================

st.markdown(
    '<div class="main-title">🍳 Chef AI</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-subtitle">'
    'Turn your ideas and ingredients into delicious recipes.'
    '</div>',
    unsafe_allow_html=True,
)


# ============================================================
# HOME PAGE
# ============================================================

if st.session_state.page == "Home":

    st.markdown(
        """
        <div class="recipe-card">

            <h2>What would you like to cook?</h2>

            <p>
                Tell Chef AI what you want to eat,
                or enter the ingredients already
                available in your kitchen.
            </p>

        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "🍲 Find a Recipe",
            use_container_width=True,
            type="primary",
        ):

            st.session_state.page = "Find a Recipe"

            st.rerun()

    with col2:

        if st.button(
            "🥕 Use My Ingredients",
            use_container_width=True,
        ):

            st.session_state.page = "Use My Ingredients"

            st.rerun()


# ============================================================
# FIND A RECIPE PAGE
# ============================================================

elif st.session_state.page == "Find a Recipe":

    st.markdown(
        "## 🍲 Find a Recipe"
    )

    st.write(
        "Enter any dish and Chef AI will create "
        "a complete recipe for you."
    )

    dish = st.text_input(
        "What do you want to cook?",
        placeholder="Example: Chicken Biryani",
    )

    servings = st.number_input(
        "Number of servings",
        min_value=1,
        max_value=50,
        value=3,
        step=1,
    )

    if st.button(
        "✨ Generate Recipe",
        type="primary",
        use_container_width=True,
    ):

        if not dish.strip():

            st.warning(
                "Please enter a dish name."
            )

        else:

            with st.spinner(
                "Chef AI is preparing your recipe..."
            ):

                try:

                    recipe = generate_recipe(
                        dish.strip(),
                        int(servings),
                    )

                    st.session_state.recipe = recipe

                except Exception as error:

                    st.error(
                        f"Sorry, we couldn't generate "
                        f"the recipe.\n\n{error}"
                    )

    if st.session_state.recipe:

        render_recipe(
            st.session_state.recipe
        )


# ============================================================
# USE MY INGREDIENTS PAGE
# ============================================================

elif st.session_state.page == "Use My Ingredients":

    st.markdown(
        "## 🥕 Use My Ingredients"
    )

    st.write(
        "Enter the ingredients you already have "
        "and Chef AI will suggest dishes."
    )

    ingredients_text = st.text_area(
        "What ingredients do you have?",
        placeholder=(
            "Example: chicken, onion, butter, "
            "garlic, rice"
        ),
        height=120,
    )

    servings = st.number_input(
        "Number of servings",
        min_value=1,
        max_value=50,
        value=3,
        step=1,
        key="ingredient_servings",
    )

    if st.button(
        "🔎 Find Recipes",
        type="primary",
        use_container_width=True,
    ):

        if not ingredients_text.strip():

            st.warning(
                "Please enter at least one ingredient."
            )

        else:

            ingredients = [
                item.strip()
                for item in ingredients_text.split(",")
                if item.strip()
            ]

            with st.spinner(
                "Finding recipes from your ingredients..."
            ):

                try:

                    recipes = find_recipes_from_ingredients(
                        ingredients,
                        int(servings),
                    )

                    st.session_state.suggestions = recipes

                except Exception as error:

                    st.error(
                        f"Sorry, we couldn't find recipes "
                        f"right now.\n\n{error}"
                    )

    suggestions = (
        st.session_state.suggestions
    )

    if suggestions:

        st.markdown(
            "### 🍽️ Recipes You Can Make"
        )

        for index, suggestion in enumerate(
            suggestions
        ):

            name = suggestion.get(
                "name",
                "Untitled Recipe",
            )

            description = suggestion.get(
                "description",
                "",
            )

            match_percentage = suggestion.get(
                "match_percentage",
                "",
            )

            uses = suggestion.get(
                "uses",
                [],
            )

            missing = suggestion.get(
                "missing",
                [],
            )

            with st.container(
                border=True
            ):

                st.markdown(
                    f"### 🍽️ {name}"
                )

                if description:

                    st.write(
                        description
                    )

                if match_percentage != "":

                    st.write(
                        f"🟢 Ingredient match: "
                        f"**{match_percentage}%**"
                    )

                if uses:

                    st.write(
                        "**You already have:** "
                        + ", ".join(
                            str(item)
                            for item in uses
                        )
                    )

                if missing:

                    st.write(
                        "**You may need:** "
                        + ", ".join(
                            str(item)
                            for item in missing
                        )
                    )

                if st.button(
                    "🍳 Make This Recipe",
                    key=f"make_recipe_{index}",
                    use_container_width=True,
                ):

                    with st.spinner(
                        f"Creating {name}..."
                    ):

                        try:

                            recipe = generate_recipe(
                                name,
                                int(servings),
                            )

                            st.session_state.recipe = recipe

                            st.session_state.page = (
                                "Find a Recipe"
                            )

                            st.rerun()

                        except Exception as error:

                            st.error(
                                f"Could not generate "
                                f"the recipe.\n\n{error}"
                            )


# ============================================================
# FAVORITES PAGE
# ============================================================

elif st.session_state.page == "Favorites":

    st.markdown(
        "## ❤️ Favorites"
    )

    favorites = (
        st.session_state.favorites
    )

    if not favorites:

        st.info(
            "You don't have any saved recipes yet."
        )

        st.write(
            "Generate a recipe and click "
            "\"Save to Favorites\"."
        )

    else:

        for index, recipe in enumerate(
            favorites
        ):

            recipe_name = recipe.get(
                "name",
                "Recipe",
            )

            with st.container(
                border=True
            ):

                st.markdown(
                    f"### 🍽️ {recipe_name}"
                )

                if st.button(
                    "View Recipe",
                    key=f"view_favorite_{index}",
                    use_container_width=True,
                ):

                    st.session_state.recipe = recipe

                    st.session_state.page = (
                        "Find a Recipe"
                    )

                    st.rerun()


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    """
    <div class="app-footer">
        Chef AI • Streamlit • Groq API
    </div>
    """,
    unsafe_allow_html=True,
)
