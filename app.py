import json
import os
import re
from typing import Any, Dict, List

import requests
import streamlit as st


# ============================================================
# APP CONFIG
# ============================================================

st.set_page_config(
    page_title="Chef AI",
    page_icon="🍳",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# GROQ CONFIG
# ============================================================

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-20b"


# ============================================================
# STYLING
# ============================================================

st.markdown(
    """
    <style>
        .stApp {
            background: #fffaf3;
        }

        .main-title {
            font-size: 48px;
            font-weight: 800;
            color: #3b2418;
            margin-bottom: 5px;
        }

        .subtitle {
            color: #765b4b;
            font-size: 18px;
            margin-bottom: 25px;
        }

        .recipe-card {
            background: white;
            padding: 25px;
            border-radius: 18px;
            border: 1px solid #eadfd5;
            box-shadow: 0 4px 18px rgba(70, 45, 30, 0.06);
            margin-bottom: 20px;
        }

        .recipe-title {
            font-size: 34px;
            font-weight: 800;
            color: #3b2418;
        }

        .section-title {
            font-size: 24px;
            font-weight: 700;
            color: #4a2e20;
            margin-top: 20px;
            margin-bottom: 10px;
        }

        .info-box {
            background: #fff3e6;
            padding: 15px;
            border-radius: 12px;
            margin: 10px 0;
        }

        .ingredient {
            padding: 8px 0;
            border-bottom: 1px solid #f0e5dc;
        }

        .step {
            background: #fffaf5;
            padding: 12px;
            border-radius: 10px;
            margin-bottom: 10px;
        }

        footer {
            visibility: hidden;
        }

        @media (max-width: 768px) {
            .main-title {
                font-size: 36px;
            }

            .recipe-title {
                font-size: 27px;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# API KEY
# ============================================================

def get_api_key() -> str:
    """
    Get the Groq API key from Streamlit Secrets first,
    then from environment variables.

    Expected key:
        GROQ_API_KEY = "gsk_..."
    """

    try:
        key = st.secrets.get("GROQ_API_KEY", "")
    except Exception:
        key = ""

    if key:
        return str(key).strip()

    return os.getenv("GROQ_API_KEY", "").strip()


# ============================================================
# GROQ API CALL
# ============================================================

def call_groq(prompt: str) -> str:
    api_key = get_api_key()

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is missing. "
            "Add your gsk_... Groq key in Streamlit Secrets."
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
                    "Create practical, accurate, delicious and beginner-friendly "
                    "recipes. Follow the requested JSON format exactly when JSON "
                    "is requested. Never include markdown fences around JSON."
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
            GROQ_URL,
            headers=headers,
            json=payload,
            timeout=90,
        )
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Could not connect to Groq: {exc}"
        ) from exc

    if response.status_code != 200:
        try:
            error_data = response.json()
            error_message = error_data.get("error", error_data)
        except Exception:
            error_message = response.text

        raise RuntimeError(
            f"Groq API error ({response.status_code}): {error_message}"
        )

    try:
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as exc:
        raise RuntimeError(
            "Groq returned an unexpected response."
        ) from exc


# ============================================================
# JSON EXTRACTION
# ============================================================

def extract_json(text: str) -> Any:
    """
    Extract JSON even if the model accidentally adds extra text
    or markdown code fences.
    """

    text = text.strip()

    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
        flags=re.IGNORECASE,
    )

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find a JSON object.
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]

        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # Try to find a JSON array.
    start = text.find("[")
    end = text.rfind("]")

    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]

        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    raise ValueError("The AI returned invalid JSON.")


# ============================================================
# RECIPE GENERATION
# ============================================================

def generate_recipe(dish: str, servings: int) -> Dict[str, Any]:
    prompt = f"""
Create a complete cooking recipe for:

Dish: {dish}
Number of servings: {servings}

Return ONLY valid JSON using exactly this structure:

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
        "Step 1",
        "Step 2",
        "Step 3"
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

Requirements:

- Quantities must be appropriate for exactly {servings} servings.
- Include realistic measurements.
- Give clear beginner-friendly steps.
- Include prep, cooking and total time.
- Include useful tips.
- Include practical substitutions.
- Include serving suggestions.
- Include food-safety advice.
- Do not include markdown.
- Return JSON only.
"""

    result = call_groq(prompt)
    data = extract_json(result)

    if not isinstance(data, dict):
        raise ValueError("Recipe response was not a JSON object.")

    return data


# ============================================================
# INGREDIENT-BASED DISH SUGGESTIONS
# ============================================================

def suggest_dishes(ingredients: List[str], servings: int) -> List[Dict[str, Any]]:
    ingredient_text = ", ".join(ingredients)

    prompt = f"""
The user currently has these ingredients:

{ingredient_text}

They want food for {servings} people.

Suggest 6 dishes they can make.

Prioritize dishes that use the ingredients they already have.

Return ONLY valid JSON using this structure:

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
                "ingredient they need to buy"
            ]
        }}
    ]
}}

Rules:

- Prefer recipes requiring ingredients the user already has.
- Be realistic about what can actually be cooked.
- match_percentage should represent approximately how many important
  ingredients the user already has.
- Keep missing ingredients concise.
- Do not include markdown.
- Return JSON only.
"""

    result = call_groq(prompt)
    data = extract_json(result)

    if isinstance(data, dict):
        recipes = data.get("recipes", [])
    elif isinstance(data, list):
        recipes = data
    else:
        recipes = []

    return recipes


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

if "selected_suggestion" not in st.session_state:
    st.session_state.selected_suggestion = None


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown("## 🍳 Chef AI")

    st.caption("Your smart kitchen assistant")

    st.divider()

    page = st.radio(
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
        ].index(st.session_state.page),
    )

    st.session_state.page = page

    st.divider()

    st.caption("Powered by Groq API")


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">🍳 Chef AI</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">'
    "Turn ingredients and ideas into delicious recipes."
    "</div>",
    unsafe_allow_html=True,
)


# ============================================================
# HOME
# ============================================================

if st.session_state.page == "Home":

    st.markdown(
        """
        <div class="recipe-card">
            <h2>What would you like to cook?</h2>
            <p>
                Tell Chef AI what you want to eat, or enter the ingredients
                already available in your kitchen.
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
# FIND A RECIPE
# ============================================================

elif st.session_state.page == "Find a Recipe":

    st.markdown(
        "## 🍲 Find a Recipe",
        unsafe_allow_html=True,
    )

    dish = st.text_input(
        "What do you want to cook?",
        placeholder="Example: Chicken Alfredo",
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
            st.warning("Please enter a dish name.")
        else:
            with st.spinner("Chef AI is preparing your recipe..."):

                try:
                    recipe = generate_recipe(
                        dish.strip(),
                        int(servings),
                    )

                    st.session_state.recipe = recipe

                except Exception as exc:
                    st.error(
                        f"Sorry, we couldn't generate the recipe. "
                        f"{exc}"
                    )

    if st.session_state.recipe:
        render_recipe(st.session_state.recipe)


# ============================================================
# USE MY INGREDIENTS
# ============================================================

elif st.session_state.page == "Use My Ingredients":

    st.markdown(
        "## 🥕 Use My Ingredients",
        unsafe_allow_html=True,
    )

    ingredients_text = st.text_area(
        "What ingredients do you have?",
        placeholder="Example: chicken, onion, butter, garlic, rice",
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
            st.warning("Please enter at least one ingredient.")
        else:

            ingredients = [
                item.strip()
                for item in ingredients_text.split(",")
                if item.strip()
            ]

            with st.spinner("Finding recipes from your ingredients..."):

                try:
                    suggestions = suggest_dishes(
                        ingredients,
                        int(servings),
                    )

                    st.session_state.suggestions = suggestions

                except Exception as exc:
                    st.error(
                        f"Sorry, we couldn't find recipes right now. "
                        f"{exc}"
                    )

    suggestions = st.session_state.suggestions

    if suggestions:

        st.markdown("### 🍽️ Recipes you can make")

        for index, suggestion in enumerate(suggestions):

            name = suggestion.get(
                "name",
                "Untitled recipe",
            )

            description = suggestion.get(
                "description",
                "",
            )

            match = suggestion.get(
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

            with st.container(border=True):

                st.markdown(
                    f"### {name}"
                )

                if description:
                    st.write(description)

                if match != "":
                    st.caption(
                        f"🟢 Ingredient match: {match}%"
                    )

                if uses:
                    st.write(
                        "**You already have:** "
                        + ", ".join(uses)
                    )

                if missing:
                    st.write(
                        "**You may need:** "
                        + ", ".join(missing)
                    )

                if st.button(
                    "🍳 Make this recipe",
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
                            st.session_state.page = "Find a Recipe"

                            st.rerun()

                        except Exception as exc:
                            st.error(
                                f"Could not generate recipe: {exc}"
                            )


# ============================================================
# FAVORITES
# ============================================================

elif st.session_state.page == "Favorites":

    st.markdown(
        "## ❤️ Favorites",
        unsafe_allow_html=True,
    )

    favorites = st.session_state.favorites

    if not favorites:
        st.info(
            "You don't have any saved recipes yet."
        )

    else:

        for index, recipe in enumerate(favorites):

            st.markdown(
                f"### 🍽️ {recipe.get('name', 'Recipe')}"
            )

            if st.button(
                "View recipe",
                key=f"favorite_view_{index}",
                use_container_width=True,
            ):
                st.session_state.recipe = recipe
                render_recipe(recipe)

            st.divider()


# ============================================================
# RECIPE RENDERER
# ============================================================

def render_recipe(recipe: Dict[str, Any]):

    if not recipe:
        return

    st.markdown("---")

    st.markdown(
        f'<div class="recipe-title">'
        f'{recipe.get("name", "Recipe")}'
        f'</div>',
        unsafe_allow_html=True,
    )

    description = recipe.get(
        "description",
        "",
    )

    if description:
        st.write(description)

    # --------------------------------------------------------
    # Recipe info
    # --------------------------------------------------------

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Servings",
            recipe.get("servings", "-"),
        )

    with col2:
        st.metric(
            "Prep",
            recipe.get("prep_time", "-"),
        )

    with col3:
        st.metric(
            "Cook",
            recipe.get("cook_time", "-"),
        )

    with col4:
        st.metric(
            "Difficulty",
            recipe.get("difficulty", "-"),
        )

    # --------------------------------------------------------
    # Favorite
    # --------------------------------------------------------

    recipe_name = recipe.get(
        "name",
        "Recipe",
    )

    already_saved = any(
        item.get("name") == recipe_name
        for item in st.session_state.favorites
    )

    if already_saved:

        if st.button(
            "💔 Remove from Favorites",
            use_container_width=True,
        ):

            st.session_state.favorites = [
                item
                for item in st.session_state.favorites
                if item.get("name") != recipe_name
            ]

            st.success(
                "Removed from favorites."
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
        '<div class="section-title">🧺 Ingredients</div>',
        unsafe_allow_html=True,
    )

    ingredients = recipe.get(
        "ingredients",
        [],
    )

    for ingredient in ingredients:

        if isinstance(ingredient, dict):

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

            text = f"**{quantity}** {item}"

            if notes:
                text += f" — {notes}"

            st.markdown(
                f'<div class="ingredient">{text}</div>',
                unsafe_allow_html=True,
            )

        else:

            st.markdown(
                f'<div class="ingredient">'
                f'{ingredient}'
                f'</div>',
                unsafe_allow_html=True,
            )

    # --------------------------------------------------------
    # Steps
    # --------------------------------------------------------

    st.markdown(
        '<div class="section-title">👨‍🍳 Instructions</div>',
        unsafe_allow_html=True,
    )

    steps = recipe.get(
        "steps",
        [],
    )

    for index, step in enumerate(steps, start=1):

        st.markdown(
            f"""
            <div class="step">
                <strong>Step {index}</strong><br>
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
            '<div class="section-title">💡 Tips</div>',
            unsafe_allow_html=True,
        )

        for tip in tips:
            st.write(f"• {tip}")

    # --------------------------------------------------------
    # Substitutions
    # --------------------------------------------------------

    substitutions = recipe.get(
        "substitutions",
        [],
    )

    if substitutions:

        st.markdown(
            '<div class="section-title">🔄 Substitutions</div>',
            unsafe_allow_html=True,
        )

        for substitution in substitutions:

            if isinstance(substitution, dict):

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
                st.write(f"• {substitution}")

    # --------------------------------------------------------
    # Serving suggestions
    # --------------------------------------------------------

    serving_suggestions = recipe.get(
        "serving_suggestions",
        [],
    )

    if serving_suggestions:

        st.markdown(
            '<div class="section-title">🍽️ Serving Suggestions</div>',
            unsafe_allow_html=True,
        )

        for suggestion in serving_suggestions:
            st.write(f"• {suggestion}")

    # --------------------------------------------------------
    # Food safety
    # --------------------------------------------------------

    food_safety = recipe.get(
        "food_safety",
        [],
    )

    if food_safety:

        st.markdown(
            '<div class="section-title">🛡️ Food Safety</div>',
            unsafe_allow_html=True,
        )

        for safety in food_safety:
            st.write(f"• {safety}")

    # --------------------------------------------------------
    # Print/share
    # --------------------------------------------------------

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:

        st.info(
            "🖨️ Use your browser's Print option "
            "to print this recipe."
        )

    with col2:

        st.info(
            "🔗 You can copy the page URL "
            "to share the recipe."
        )


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    """
    <br><br>
    <div style="
        text-align:center;
        color:#8a7568;
        font-size:14px;
        padding:20px;
    ">
        Chef AI • Streamlit • Groq API
    </div>
    """,
    unsafe_allow_html=True,
)
