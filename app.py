
import os
import re
from typing import Any, Dict, List

import requests
import streamlit as st


# -----------------------------
# App configuration
# -----------------------------
st.set_page_config(
    page_title="Chef AI — Kitchen Assistant",
    page_icon="🍳",
    layout="wide",
    initial_sidebar_state="collapsed",
)

XAI_URL = "https://api.x.ai/v1/responses"
DEFAULT_MODEL = "grok-4.6"


# -----------------------------
# Styling — Streamlit only
# -----------------------------
st.markdown(
    """
    <style>
    .stApp {
        background: #fffaf5;
    }

    .main .block-container {
        max-width: 1180px;
        padding-top: 1.2rem;
        padding-bottom: 4rem;
    }

    .hero {
        padding: 3.2rem 1.5rem 2.8rem 1.5rem;
        border-radius: 28px;
        background: linear-gradient(135deg, #fff1dc 0%, #ffe7c2 100%);
        text-align: center;
        margin-bottom: 1.5rem;
        border: 1px solid #f4d6aa;
    }

    .hero h1 {
        font-size: 3.2rem;
        margin-bottom: .4rem;
        color: #3c2415;
        font-weight: 800;
    }

    .hero p {
        font-size: 1.15rem;
        color: #704b32;
        max-width: 700px;
        margin: 0 auto;
    }

    .feature-card {
        background: white;
        border: 1px solid #f0dfce;
        border-radius: 22px;
        padding: 1.5rem;
        min-height: 180px;
        box-shadow: 0 8px 28px rgba(86, 55, 28, .07);
    }

    .feature-card h3 {
        color: #3c2415;
        margin-bottom: .45rem;
    }

    .feature-card p {
        color: #76563f;
        line-height: 1.6;
    }

    .recipe-box {
        background: white;
        border: 1px solid #ead9c7;
        border-radius: 22px;
        padding: 1.6rem;
        margin-top: 1rem;
        box-shadow: 0 8px 30px rgba(86, 55, 28, .06);
    }

    .recipe-title {
        font-size: 2rem;
        font-weight: 800;
        color: #3c2415;
        margin-bottom: .2rem;
    }

    .muted {
        color: #76563f;
    }

    .suggestion-card {
        background: white;
        border: 1px solid #ead9c7;
        border-radius: 18px;
        padding: 1.1rem;
        margin-bottom: .8rem;
    }

    .missing {
        color: #9b5b22;
    }

    .available {
        color: #477a3f;
    }

    .footer {
        text-align: center;
        color: #8b735f;
        padding: 2rem 0 0;
        font-size: .9rem;
    }

    div[data-testid="stMetric"] {
        background: #fffdfb;
        border: 1px solid #eee0d2;
        padding: .7rem;
        border-radius: 14px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------
# State
# -----------------------------
defaults = {
    "page": "Home",
    "recipe": None,
    "suggestions": [],
    "last_dish": "",
    "last_ingredients": "",
    "last_servings": 4,
    "favorites": [],
    "selected_suggestion": None,
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# -----------------------------
# API helpers
# -----------------------------
def get_api_key() -> str:
    """Read the Grok/xAI key from Streamlit secrets or environment."""
    try:
        secret_key = st.secrets.get("XAI_API_KEY", "")
    except Exception:
        secret_key = ""

    return secret_key or os.getenv("XAI_API_KEY", "")


def extract_response_text(data: Dict[str, Any]) -> str:
    """Extract text from xAI Responses API in a defensive way."""
    if isinstance(data.get("output_text"), str) and data["output_text"].strip():
        return data["output_text"].strip()

    pieces: List[str] = []
    for item in data.get("output", []) or []:
        for content in item.get("content", []) or []:
            text = content.get("text")
            if isinstance(text, str):
                pieces.append(text)
    return "\n".join(pieces).strip()


def call_grok(prompt: str) -> str:
    api_key = get_api_key()

    if not api_key:
        raise RuntimeError(
            "XAI_API_KEY is not configured. Add it to Streamlit secrets or the server environment."
        )

    payload = {
        "model": DEFAULT_MODEL,
        "input": [
            {
                "role": "system",
                "content": (
                    "You are Chef AI, a practical and careful kitchen assistant. "
                    "Give realistic recipes, sensible measurements, beginner-friendly "
                    "steps, substitutions, and food-safety notes when relevant. "
                    "Never invent that the user owns ingredients they did not list."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }

    response = requests.post(
        XAI_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )

    if not response.ok:
        try:
            detail = response.json()
        except Exception:
            detail = response.text
        raise RuntimeError(f"Grok API error ({response.status_code}): {detail}")

    data = response.json()
    text = extract_response_text(data)
    if not text:
        raise RuntimeError("Grok returned an empty response.")
    return text


def clean_json_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text, flags=re.I)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def call_grok_json(prompt: str) -> Dict[str, Any]:
    text = call_grok(
        prompt
        + "\n\nIMPORTANT: Return ONLY valid JSON. No markdown fences and no extra commentary."
    )
    cleaned = clean_json_text(text)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to recover the first JSON object.
        match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if match:
            return json.loads(match.group(0))
        raise RuntimeError("The AI returned an invalid JSON response. Please try again.")


# -----------------------------
# AI functions
# -----------------------------
def generate_recipe(dish: str, servings: int) -> Dict[str, Any]:
    prompt = f"""
Create a complete recipe for "{dish}" for exactly {servings} servings.

Return this JSON structure:
{{
  "name": "string",
  "description": "string",
  "servings": {servings},
  "prep_time": "string",
  "cook_time": "string",
  "total_time": "string",
  "difficulty": "Easy | Medium | Hard",
  "ingredients": [
    {{"item": "string", "quantity": "string"}}
  ],
  "instructions": ["step 1", "step 2"],
  "tips": ["tip 1", "tip 2"],
  "substitutions": ["optional substitution"],
  "serving_suggestions": ["suggestion"],
  "food_safety": ["relevant safety note"]
}}

Requirements:
- Scale ingredient quantities for exactly {servings} servings.
- Use practical measurements.
- Keep instructions clear for a beginner.
- Do not add a fake rating.
- If a dish name is ambiguous, choose the most common culinary interpretation.
"""
    result = call_grok_json(prompt)
    result["servings"] = servings
    return result


def find_recipes(ingredients: List[str], servings: int) -> List[Dict[str, Any]]:
    prompt = f"""
The user has these ingredients:
{", ".join(ingredients)}

They want ideas for approximately {servings} servings.

Suggest 6 practical dishes that use as many of the listed ingredients as reasonably
possible. Recipes may have 1-4 missing ingredients, but clearly identify them.

Return:
{{
  "recipes": [
    {{
      "name": "string",
      "description": "short string",
      "cooking_time": "string",
      "difficulty": "Easy | Medium | Hard",
      "uses": ["ingredients from user's list"],
      "missing": ["important ingredients not in user's list"]
    }}
  ]
}}

Prioritize recipes by ingredient match. Do not suggest obviously incompatible combinations.
"""
    result = call_grok_json(prompt)
    recipes = result.get("recipes", [])
    return recipes if isinstance(recipes, list) else []


# -----------------------------
# Utility functions
# -----------------------------
def save_favorite(recipe: Dict[str, Any]) -> None:
    name = recipe.get("name", "Recipe")
    if not any(r.get("name") == name for r in st.session_state.favorites):
        st.session_state.favorites.append(recipe)


def render_recipe(recipe: Dict[str, Any], source: str = "") -> None:
    st.markdown('<div class="recipe-box">', unsafe_allow_html=True)

    st.markdown(
        f'<div class="recipe-title">🍽️ {recipe.get("name", "Recipe")}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="muted">{recipe.get("description", "")}</div>',
        unsafe_allow_html=True,
    )

    st.write("")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Servings", recipe.get("servings", 4))
    c2.metric("Prep", recipe.get("prep_time", "—"))
    c3.metric("Cook", recipe.get("cook_time", "—"))
    c4.metric("Difficulty", recipe.get("difficulty", "—"))

    st.markdown("### 🧺 Ingredients")
    ingredients = recipe.get("ingredients", [])
    for idx, ing in enumerate(ingredients):
        item = ing.get("item", "")
        quantity = ing.get("quantity", "")
        st.checkbox(
            f"**{quantity}** — {item}",
            key=f"ingredient_{id(recipe)}_{idx}",
        )

    st.markdown("### 👨‍🍳 Instructions")
    for idx, step in enumerate(recipe.get("instructions", []), 1):
        st.markdown(f"**{idx}.** {step}")

    tips = recipe.get("tips", [])
    if tips:
        st.markdown("### 💡 Cooking Tips")
        for tip in tips:
            st.markdown(f"- {tip}")

    substitutions = recipe.get("substitutions", [])
    if substitutions:
        st.markdown("### 🔄 Substitutions")
        for item in substitutions:
            st.markdown(f"- {item}")

    serving_suggestions = recipe.get("serving_suggestions", [])
    if serving_suggestions:
        st.markdown("### 🍴 Serving Suggestions")
        for item in serving_suggestions:
            st.markdown(f"- {item}")

    safety = recipe.get("food_safety", [])
    if safety:
        st.markdown("### ⚠️ Food Safety")
        for item in safety:
            st.markdown(f"- {item}")

    st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    b1, b2, b3, b4 = st.columns(4)

    if b1.button("❤️ Save Recipe", use_container_width=True, key=f"save_{id(recipe)}"):
        save_favorite(recipe)
        st.success("Recipe saved to Favorites.")

    if b2.button("🔄 Generate Again", use_container_width=True, key=f"again_{id(recipe)}"):
        dish = recipe.get("name", st.session_state.last_dish)
        with st.spinner("Chef AI is preparing your recipe..."):
            try:
                st.session_state.recipe = generate_recipe(
                    dish, int(recipe.get("servings", st.session_state.last_servings))
                )
                st.rerun()
            except Exception as exc:
                st.error("Sorry, we couldn't generate your recipe right now. Please try again.")
                st.caption(str(exc))

    if b3.button("🖨️ Print Recipe", use_container_width=True, key=f"print_{id(recipe)}"):
        st.info("Use your browser's Print command (Ctrl+P / Cmd+P) to print this recipe.")

    if b4.button("📤 Share", use_container_width=True, key=f"share_{id(recipe)}"):
        st.info("Share the recipe by copying the page URL or using your browser's share option.")

    st.markdown("### 👥 Adjust Servings")
    current = int(recipe.get("servings", 4))
    a, b, c = st.columns([1, 2, 1])
    if a.button("➖", key=f"minus_{id(recipe)}", use_container_width=True):
        current = max(1, current - 1)
    b.markdown(f"<h4 style='text-align:center'>{current} servings</h4>", unsafe_allow_html=True)
    if c.button("➕", key=f"plus_{id(recipe)}", use_container_width=True):
        current += 1

    if current != int(recipe.get("servings", 4)):
        if st.button("Recalculate Ingredients", key=f"scale_{id(recipe)}"):
            with st.spinner("Recalculating quantities..."):
                try:
                    new_recipe = generate_recipe(recipe.get("name", "Recipe"), current)
                    st.session_state.recipe = new_recipe
                    st.rerun()
                except Exception as exc:
                    st.error("Sorry, we couldn't recalculate the recipe. Please try again.")
                    st.caption(str(exc))


# -----------------------------
# Sidebar navigation
# -----------------------------
with st.sidebar:
    st.markdown("## 🍳 Chef AI")
    page = st.radio(
        "Navigation",
        ["Home", "Find a Recipe", "Use My Ingredients", "Favorites"],
        index=["Home", "Find a Recipe", "Use My Ingredients", "Favorites"].index(
            st.session_state.page
        ),
    )
    st.session_state.page = page

    st.divider()
    st.caption("AI recipes powered by Grok through the xAI API.")


# -----------------------------
# Home
# -----------------------------
if st.session_state.page == "Home":
    st.markdown(
        """
        <div class="hero">
            <h1>🍳 Your AI Kitchen Assistant</h1>
            <p>
                Tell us what you want to cook or what ingredients you have.
                Chef AI will help you decide what to make and create a complete recipe.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns(2)

    with left:
        st.markdown(
            """
            <div class="feature-card">
                <h3>🍲 What do you want to cook?</h3>
                <p>Choose a dish and the number of people. Get a complete recipe with quantities, steps, tips and substitutions.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Generate Recipe →", use_container_width=True, type="primary"):
            st.session_state.page = "Find a Recipe"
            st.rerun()

    with right:
        st.markdown(
            """
            <div class="feature-card">
                <h3>🧺 What do you have in your kitchen?</h3>
                <p>Enter your available ingredients and discover practical dishes you can make with them.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Find Recipes →", use_container_width=True):
            st.session_state.page = "Use My Ingredients"
            st.rerun()

    st.write("")
    st.markdown("### ✨ How it works")
    x1, x2, x3 = st.columns(3)
    x1.markdown("**1. Tell us**  \nEnter a dish or your available ingredients.")
    x2.markdown("**2. Chef AI thinks**  \nGrok analyzes servings, ingredients and recipe options.")
    x3.markdown("**3. Start cooking**  \nFollow the clear, step-by-step recipe.")

# -----------------------------
# Find a Recipe
# -----------------------------
elif st.session_state.page == "Find a Recipe":
    st.title("🍲 What do you want to cook?")
    st.write("Tell Chef AI the dish and how many people you're cooking for.")

    dish = st.text_input(
        "Dish name",
        value=st.session_state.last_dish,
        placeholder="e.g. Chicken Biryani",
    )
    servings = st.number_input(
        "Number of people / servings",
        min_value=1,
        max_value=100,
        value=int(st.session_state.last_servings),
        step=1,
    )

    if st.button("✨ Generate Recipe", type="primary", use_container_width=True):
        if not dish.strip():
            st.warning("Please enter a dish name.")
        elif servings < 1:
            st.warning("Please select at least 1 serving.")
        else:
            st.session_state.last_dish = dish.strip()
            st.session_state.last_servings = int(servings)

            with st.spinner("Chef AI is preparing your recipe..."):
                try:
                    st.session_state.recipe = generate_recipe(dish.strip(), int(servings))
                    st.rerun()
                except Exception as exc:
                    st.error("Sorry, we couldn't generate your recipe right now. Please try again.")
                    st.caption(str(exc))

    if st.session_state.recipe:
        render_recipe(st.session_state.recipe)

# -----------------------------
# Use My Ingredients
# -----------------------------
elif st.session_state.page == "Use My Ingredients":
    st.title("🧺 What can I cook with what I have?")
    st.write("Enter the ingredients currently available in your kitchen.")

    ingredients_text = st.text_area(
        "Your ingredients",
        value=st.session_state.last_ingredients,
        placeholder="chicken, onion, tomato, potato, rice, garlic, ginger",
        height=110,
    )
    servings = st.number_input(
        "How many people?",
        min_value=1,
        max_value=100,
        value=int(st.session_state.last_servings),
        step=1,
    )

    ingredients = [
        item.strip()
        for item in ingredients_text.split(",")
        if item.strip()
    ]

    if ingredients:
        st.markdown("**Your ingredients:**")
        chip_cols = st.columns(min(len(ingredients), 5))
        for i, ingredient in enumerate(ingredients):
            chip_cols[i % len(chip_cols)].markdown(f"`{ingredient}`")

    if st.button("🔎 Find Recipes", type="primary", use_container_width=True):
        if not ingredients:
            st.warning("Please enter at least one ingredient.")
        else:
            st.session_state.last_ingredients = ingredients_text
            st.session_state.last_servings = int(servings)

            with st.spinner("Chef AI is finding dishes you can make..."):
                try:
                    st.session_state.suggestions = find_recipes(ingredients, int(servings))
                    st.rerun()
                except Exception as exc:
                    st.error("Sorry, we couldn't find recipes right now. Please try again.")
                    st.caption(str(exc))

    if st.session_state.suggestions:
        st.markdown("### 🍽️ You can make...")
        for i, suggestion in enumerate(st.session_state.suggestions):
            st.markdown('<div class="suggestion-card">', unsafe_allow_html=True)
            st.markdown(f"### {suggestion.get('name', 'Recipe')}")
            st.write(suggestion.get("description", ""))

            m1, m2 = st.columns(2)
            m1.write(f"**Time:** {suggestion.get('cooking_time', '—')}")
            m2.write(f"**Difficulty:** {suggestion.get('difficulty', '—')}")

            uses = suggestion.get("uses", [])
            missing = suggestion.get("missing", [])

            if uses:
                st.markdown(
                    '<span class="available"><b>Uses:</b> '
                    + ", ".join(uses)
                    + "</span>",
                    unsafe_allow_html=True,
                )

            if missing:
                st.markdown(
                    '<span class="missing"><b>Missing:</b> '
                    + ", ".join(missing)
                    + "</span>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown('<span class="available"><b>You have everything important.</b></span>', unsafe_allow_html=True)

            if st.button("View Recipe", key=f"view_{i}", use_container_width=True):
                with st.spinner("Chef AI is preparing your recipe..."):
                    try:
                        st.session_state.recipe = generate_recipe(
                            suggestion.get("name", "Recipe"), int(servings)
                        )
                        st.session_state.page = "Find a Recipe"
                        st.rerun()
                    except Exception as exc:
                        st.error("Sorry, we couldn't generate that recipe right now. Please try again.")
                        st.caption(str(exc))

            st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------
# Favorites
# -----------------------------
elif st.session_state.page == "Favorites":
    st.title("❤️ Favorites")

    if not st.session_state.favorites:
        st.info("You haven't saved any recipes yet. Generate a recipe and click “Save Recipe”.")
    else:
        for i, recipe in enumerate(st.session_state.favorites):
            with st.expander(f"🍽️ {recipe.get('name', 'Recipe')} — {recipe.get('servings', '—')} servings"):
                st.write(recipe.get("description", ""))
                st.write(
                    f"**Prep:** {recipe.get('prep_time', '—')}  |  "
                    f"**Cook:** {recipe.get('cook_time', '—')}  |  "
                    f"**Difficulty:** {recipe.get('difficulty', '—')}"
                )
                c1, c2 = st.columns(2)
                if c1.button("Open Recipe", key=f"openfav_{i}", use_container_width=True):
                    st.session_state.recipe = recipe
                    st.session_state.page = "Find a Recipe"
                    st.rerun()
                if c2.button("Remove", key=f"removefav_{i}", use_container_width=True):
                    st.session_state.favorites.pop(i)
                    st.rerun()


st.markdown(
    '<div class="footer">Chef AI • Streamlit • Grok via xAI</div>',
    unsafe_allow_html=True,
)
