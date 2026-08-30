async function fetchJson(url) {
    const response = await fetch(url);

    if (!response.ok) {
        const message = await response.text();

        throw new Error(
            `${url}: ${message || response.status}`
        );
    }

    return response.json();
}


function setText(id, value) {
    const element = document.getElementById(id);

    if (element) {
        element.textContent = value;
    }
}


async function loadDashboard() {
    const errorElement =
        document.getElementById("dashboard-error");

    try {
        const [
            inventory,
            pantry,
            settings,
            favorites
        ] = await Promise.all([
            fetchJson("/api/inventory"),
            fetchJson("/api/pantry"),
            fetchJson("/api/settings"),
            fetchJson(
                "/api/recipes?favorite=true"
            )
        ]);

        setText(
            "fridge-count",
            inventory.items.length
        );

        setText(
            "pantry-count",
            pantry.items.length
        );

        setText(
            "favorite-count",
            favorites.recipes.length
        );

        setText(
            "planning-days",
            settings.planning_days
        );

        setText(
            "people",
            settings.people
        );

        setText(
            "plan-lunch",
            settings.plan_lunch
                ? "Oui"
                : "Non"
        );

        setText(
            "plan-dinner",
            settings.plan_dinner
                ? "Oui"
                : "Non"
        );

        setText(
            "weekday-time",
            `${settings.weekday_max_cooking_minutes} min`
        );

    } catch (error) {
        console.error(error);

        errorElement.textContent =
            "Impossible de charger toutes les données du dashboard.";

        errorElement.hidden = false;
    }
}


loadDashboard();