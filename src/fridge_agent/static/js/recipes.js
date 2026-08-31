let recipes = [];
let selectedRecipe = null;


const errorElement =
    document.getElementById("recipes-error");

const successElement =
    document.getElementById("recipes-success");

const emptyElement =
    document.getElementById("recipes-empty");

const noResultElement =
    document.getElementById("recipes-no-result");

const contentElement =
    document.getElementById("recipes-content");

const gridElement =
    document.getElementById("recipes-grid");

const summaryElement =
    document.getElementById("recipes-summary");

const searchInput =
    document.getElementById("recipe-search");

const favoriteOnlyInput =
    document.getElementById("favorite-only");

const dialog =
    document.getElementById(
        "saved-recipe-dialog"
    );

const favoriteButton =
    document.getElementById(
        "toggle-saved-recipe-favorite"
    );


async function fetchJson(
    url,
    options = {}
) {
    const response =
        await fetch(
            url,
            options
        );

    if (!response.ok) {
        const message =
            await response.text();

        throw new Error(
            message ||
            `HTTP ${response.status}`
        );
    }

    return response.json();
}


function hideMessages() {
    errorElement.hidden = true;
    successElement.hidden = true;
}


function unitLabel(unit) {
    const labels = {
        piece: "pièce",
        g: "g",
        kg: "kg",
        ml: "ml",
        l: "l",
        pack: "paquet",
        bottle: "bouteille",
        jar: "bocal",
        can: "boîte"
    };

    return labels[unit] ?? unit;
}


function totalMinutes(recipe) {
    return (
        recipe.preparation_minutes +
        recipe.cooking_minutes
    );
}


function matchesSearch(
    recipe,
    search
) {
    if (!search) {
        return true;
    }

    const normalizedSearch =
        search
            .trim()
            .toLocaleLowerCase(
                "fr-FR"
            );

    if (!normalizedSearch) {
        return true;
    }

    if (
        recipe.title
            .toLocaleLowerCase(
                "fr-FR"
            )
            .includes(
                normalizedSearch
            )
    ) {
        return true;
    }

    return recipe.ingredients.some(
        ingredient =>
            ingredient.name
                .toLocaleLowerCase(
                    "fr-FR"
                )
                .includes(
                    normalizedSearch
                )
    );
}


function visibleRecipes() {
    return recipes.filter(
        recipe => {
            if (
                favoriteOnlyInput.checked &&
                !recipe.is_favorite
            ) {
                return false;
            }

            return matchesSearch(
                recipe,
                searchInput.value
            );
        }
    );
}


function ingredientPreview(recipe) {
    const names =
        recipe.ingredients
            .slice(0, 4)
            .map(
                ingredient =>
                    ingredient.name
            );

    let result =
        names.join(" · ");

    if (
        recipe.ingredients.length >
        names.length
    ) {
        result +=
            ` · +${
                recipe.ingredients.length -
                names.length
            }`;
    }

    return result;
}


function renderRecipes() {
    gridElement.innerHTML = "";

    if (recipes.length === 0) {
        emptyElement.hidden = false;
        noResultElement.hidden = true;
        contentElement.hidden = true;

        return;
    }

    emptyElement.hidden = true;

    const visible =
        visibleRecipes();

    summaryElement.textContent =
        visible.length === 1
            ? "1 recette"
            : `${visible.length} recettes`;

    if (visible.length === 0) {
        noResultElement.hidden = false;
        contentElement.hidden = true;

        return;
    }

    noResultElement.hidden = true;
    contentElement.hidden = false;

    for (const recipe of visible) {
        const card =
            document.createElement(
                "article"
            );

        card.className =
            "saved-recipe-card";

        const favorite =
            recipe.is_favorite
                ? "♥"
                : "♡";

        card.innerHTML = `
            <div class="saved-recipe-card-header">
                <div>
                    <span class="recipe-source">
                        ${
                            recipe.source ===
                            "meal_plan"
                                ? "Menu"
                                : "Recette"
                        }
                    </span>

                    <h3></h3>
                </div>

                <button
                    type="button"
                    class="recipe-favorite-button"
                    title="${
                        recipe.is_favorite
                            ? "Retirer des favoris"
                            : "Ajouter aux favoris"
                    }"
                >
                    ${favorite}
                </button>
            </div>

            <div class="saved-recipe-meta">
                <span>
                    ${recipe.servings}
                    pers.
                </span>

                <span>
                    ${totalMinutes(recipe)}
                    min
                </span>

                <span>
                    ${recipe.ingredients.length}
                    ingrédients
                </span>
            </div>

            <p class="ingredient-preview"></p>

            <button
                type="button"
                class="button secondary recipe-open-button"
            >
                Voir la recette
            </button>
        `;

        card.querySelector(
            "h3"
        ).textContent =
            recipe.title;

        card.querySelector(
            ".ingredient-preview"
        ).textContent =
            ingredientPreview(
                recipe
            );

        card.querySelector(
            ".recipe-open-button"
        ).addEventListener(
            "click",
            () => {
                openRecipe(recipe);
            }
        );

        card.querySelector(
            ".recipe-favorite-button"
        ).addEventListener(
            "click",
            async () => {
                await toggleFavorite(
                    recipe
                );
            }
        );

        gridElement.appendChild(
            card
        );
    }
}


function openRecipe(recipe) {
    selectedRecipe = recipe;

    document.getElementById(
        "saved-recipe-title"
    ).textContent =
        recipe.title;

    document.getElementById(
        "saved-recipe-meta"
    ).textContent =
        `${recipe.servings} personnes · ` +
        `${recipe.preparation_minutes} min préparation · ` +
        `${recipe.cooking_minutes} min cuisson`;

    const ingredients =
        document.getElementById(
            "saved-recipe-ingredients"
        );

    ingredients.innerHTML = "";

    for (
        const ingredient
        of recipe.ingredients
    ) {
        const row =
            document.createElement(
                "div"
            );

        row.className =
            "recipe-ingredient";

        const name =
            document.createElement(
                "span"
            );

        name.textContent =
            ingredient.name;

        const quantity =
            document.createElement(
                "strong"
            );

        quantity.textContent =
            `${ingredient.quantity} ` +
            `${unitLabel(
                ingredient.unit
            )}`;

        row.append(
            name,
            quantity
        );

        ingredients.appendChild(
            row
        );
    }

    const steps =
        document.getElementById(
            "saved-recipe-steps"
        );

    steps.innerHTML = "";

    for (
        const instruction
        of recipe.steps
    ) {
        const item =
            document.createElement(
                "li"
            );

        item.textContent =
            instruction;

        steps.appendChild(item);
    }

    const notes =
        document.getElementById(
            "saved-recipe-notes"
        );

    if (recipe.notes) {
        notes.textContent =
            recipe.notes;

        notes.hidden = false;
    } else {
        notes.hidden = true;
    }

    updateDialogFavoriteButton();

    dialog.showModal();
}


function updateDialogFavoriteButton() {
    if (!selectedRecipe) {
        return;
    }

    favoriteButton.textContent =
        selectedRecipe.is_favorite
            ? "♥ Retirer des favoris"
            : "♡ Ajouter aux favoris";
}


async function toggleFavorite(recipe) {
    hideMessages();

    const newValue =
        !recipe.is_favorite;

    try {
        await fetchJson(
            `/api/recipes/` +
            `${recipe.id}/favorite`,
            {
                method: "PUT",
                headers: {
                    "Content-Type":
                        "application/json"
                },
                body:
                    JSON.stringify({
                        favorite:
                            newValue
                    })
            }
        );

        recipe.is_favorite =
            newValue;

        if (
            selectedRecipe &&
            selectedRecipe.id ===
                recipe.id
        ) {
            selectedRecipe =
                recipe;

            updateDialogFavoriteButton();
        }

        renderRecipes();

        successElement.textContent =
            newValue
                ? "Recette ajoutée aux favoris."
                : "Recette retirée des favoris.";

        successElement.hidden =
            false;

    } catch (error) {
        console.error(error);

        errorElement.textContent =
            "Impossible de modifier le favori.";

        errorElement.hidden =
            false;
    }
}


favoriteButton.addEventListener(
    "click",
    async () => {
        if (!selectedRecipe) {
            return;
        }

        favoriteButton.disabled =
            true;

        try {
            await toggleFavorite(
                selectedRecipe
            );

        } finally {
            favoriteButton.disabled =
                false;
        }
    }
);


searchInput.addEventListener(
    "input",
    renderRecipes
);


favoriteOnlyInput.addEventListener(
    "change",
    renderRecipes
);


document.getElementById(
    "close-saved-recipe"
).addEventListener(
    "click",
    () => {
        dialog.close();
    }
);


dialog.addEventListener(
    "click",
    event => {
        if (
            event.target === dialog
        ) {
            dialog.close();
        }
    }
);


async function loadRecipes() {
    hideMessages();

    try {
        const response =
            await fetchJson(
                "/api/recipes"
            );

        recipes =
            response.recipes;

        renderRecipes();

    } catch (error) {
        console.error(error);

        errorElement.textContent =
            "Impossible de charger les recettes.";

        errorElement.hidden =
            false;
    }
}


loadRecipes();