let currentPlan = null;
let selectedMeal = null;


const errorElement =
    document.getElementById("menu-error");

const successElement =
    document.getElementById("menu-success");

const emptyElement =
    document.getElementById("menu-empty");

const menuElement =
    document.getElementById("current-menu");

const mealGrid =
    document.getElementById("meal-grid");

const generateButton =
    document.getElementById("generate-menu");

const startDateInput =
    document.getElementById("menu-start-date");

const generationStatus =
    document.getElementById("generation-status");

const dialog =
    document.getElementById("recipe-dialog");

const favoriteButton =
    document.getElementById("favorite-meal");


async function fetchJson(
    url,
    options = {}
) {
    const response = await fetch(
        url,
        options
    );

    if (!response.ok) {
        const message =
            await response.text();

        const error =
            new Error(
                message ||
                `HTTP ${response.status}`
            );

        error.status =
            response.status;

        throw error;
    }

    return response.json();
}


function hideMessages() {
    errorElement.hidden = true;
    successElement.hidden = true;
}


function localDate(
    isoDate
) {
    return new Date(
        `${isoDate}T12:00:00`
    );
}


function formatDay(
    isoDate
) {
    return localDate(
        isoDate
    ).toLocaleDateString(
        "fr-FR",
        {
            weekday: "long",
            day: "numeric",
            month: "long"
        }
    );
}


function formatShortDate(
    isoDate
) {
    return localDate(
        isoDate
    ).toLocaleDateString(
        "fr-FR",
        {
            day: "numeric",
            month: "short"
        }
    );
}


function mealTypeLabel(
    mealType
) {
    return mealType === "lunch"
        ? "Déjeuner"
        : "Dîner";
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


function renderPlan(plan) {
    currentPlan = plan;

    emptyElement.hidden = true;
    menuElement.hidden = false;

    mealGrid.innerHTML = "";

    const first =
        plan.meals[0];

    const last =
        plan.meals[
            plan.meals.length - 1
        ];

    document.getElementById(
        "menu-period"
    ).textContent =
        first && last
            ? `Du ${formatShortDate(
                first.meal_date
            )} au ${formatShortDate(
                last.meal_date
            )}`
            : "";

    document.getElementById(
        "shopping-link"
    ).href =
        `/shopping?plan=${plan.id}`;

    for (const meal of plan.meals) {
        const article =
            document.createElement(
                "article"
            );

        article.className =
            "meal-card";

        article.innerHTML = `
            <div class="meal-card-date">
                <strong>
                    ${formatDay(
                        meal.meal_date
                    )}
                </strong>

                <span>
                    ${mealTypeLabel(
                        meal.meal_type
                    )}
                </span>
            </div>

            <div class="meal-card-content">
                <h3></h3>

                <div class="meal-meta">
                    <span>
                        ${meal.servings}
                        pers.
                    </span>

                    <span>
                        ${
                            meal.preparation_minutes +
                            meal.cooking_minutes
                        }
                        min
                    </span>

                    ${
                        meal.is_favorite
                            ? `<span class="favorite-label">
                                ♥ Favori
                               </span>`
                            : ""
                    }
                </div>
            </div>

            <button
                type="button"
                class="button secondary"
            >
                Voir la recette
            </button>
        `;

        article.querySelector(
            "h3"
        ).textContent =
            meal.title;

        article.querySelector(
            "button"
        ).addEventListener(
            "click",
            () => {
                openRecipe(
                    meal
                );
            }
        );

        mealGrid.appendChild(
            article
        );
    }
}


function openRecipe(meal) {
    selectedMeal = meal;

    document.getElementById(
        "recipe-date"
    ).textContent =
        `${formatDay(
            meal.meal_date
        )} · ${mealTypeLabel(
            meal.meal_type
        )}`;

    document.getElementById(
        "recipe-title"
    ).textContent =
        meal.title;

    document.getElementById(
        "recipe-meta"
    ).textContent =
        `${meal.servings} personnes · ` +
        `${meal.preparation_minutes} min préparation · ` +
        `${meal.cooking_minutes} min cuisson`;

    const ingredients =
        document.getElementById(
            "recipe-ingredients"
        );

    ingredients.innerHTML = "";

    for (
        const ingredient
        of meal.ingredients
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
            "recipe-steps"
        );

    steps.innerHTML = "";

    for (const instruction of meal.steps) {
        const item =
            document.createElement(
                "li"
            );

        item.textContent =
            instruction;

        steps.appendChild(
            item
        );
    }

    const notes =
        document.getElementById(
            "recipe-notes"
        );

    if (meal.notes) {
        notes.textContent =
            meal.notes;

        notes.hidden = false;
    } else {
        notes.hidden = true;
    }

    updateFavoriteButton();

    dialog.showModal();
}


function updateFavoriteButton() {
    if (!selectedMeal) {
        return;
    }

    if (selectedMeal.is_favorite) {
        favoriteButton.textContent =
            "♥ Favori";

        favoriteButton.disabled =
            true;
    } else {
        favoriteButton.textContent =
            "♡ Ajouter aux favoris";

        favoriteButton.disabled =
            false;
    }
}


async function loadPlan(planId) {
    const plan =
        await fetchJson(
            `/api/meal-plans/${planId}`
        );

    renderPlan(plan);
}


async function loadLatestPlan() {
    try {
        const latest =
            await fetchJson(
                "/api/meal-plans/latest"
            );

        await loadPlan(
            latest.id
        );

    } catch (error) {
        if (error.status === 404) {
            emptyElement.hidden =
                false;

            menuElement.hidden =
                true;

            return;
        }

        console.error(error);

        errorElement.textContent =
            "Impossible de charger le menu actuel.";

        errorElement.hidden =
            false;
    }
}


function setDefaultDate() {
    const today =
        new Date();

    const year =
        today.getFullYear();

    const month =
        String(
            today.getMonth() + 1
        ).padStart(
            2,
            "0"
        );

    const day =
        String(
            today.getDate()
        ).padStart(
            2,
            "0"
        );

    startDateInput.value =
        `${year}-${month}-${day}`;
}


generateButton.addEventListener(
    "click",
    async () => {
        hideMessages();

        if (!startDateInput.value) {
            errorElement.textContent =
                "Choisissez la date du premier jour.";

            errorElement.hidden =
                false;

            return;
        }

        generateButton.disabled =
            true;

        generationStatus.textContent =
            "Génération du menu par l'IA…";

        generationStatus.hidden =
            false;

        try {
            const generated =
                await fetchJson(
                    "/api/meal-plans/generate" +
                    `?start_date=` +
                    encodeURIComponent(
                        startDateInput.value
                    ),
                    {
                        method: "POST"
                    }
                );

            await loadPlan(
                generated.id
            );

            successElement.textContent =
                "Nouveau menu généré.";

            successElement.hidden =
                false;

            generationStatus.hidden =
                true;

        } catch (error) {
            console.error(error);

            generationStatus.hidden =
                true;

            errorElement.textContent =
                `Impossible de générer le menu : ` +
                `${error.message}`;

            errorElement.hidden =
                false;

        } finally {
            generateButton.disabled =
                false;
        }
    }
);


favoriteButton.addEventListener(
    "click",
    async () => {
        if (!selectedMeal) {
            return;
        }

        favoriteButton.disabled =
            true;

        try {
            await fetchJson(
                `/api/meals/` +
                `${selectedMeal.id}/favorite`,
                {
                    method: "POST"
                }
            );

            selectedMeal.is_favorite =
                true;

            updateFavoriteButton();

            renderPlan(
                currentPlan
            );

        } catch (error) {
            console.error(error);

            errorElement.textContent =
                "Impossible d'ajouter cette recette aux favoris.";

            errorElement.hidden =
                false;

            favoriteButton.disabled =
                false;
        }
    }
);


document.getElementById(
    "close-recipe"
).addEventListener(
    "click",
    () => {
        dialog.close();
    }
);


dialog.addEventListener(
    "click",
    event => {
        if (event.target === dialog) {
            dialog.close();
        }
    }
);


setDefaultDate();
loadLatestPlan();