let currentPlanId = null;
let shoppingData = null;
let checkedItems = new Set();


const loadingElement =
    document.getElementById(
        "shopping-loading"
    );

const emptyElement =
    document.getElementById(
        "shopping-empty"
    );

const contentElement =
    document.getElementById(
        "shopping-content"
    );

const errorElement =
    document.getElementById(
        "shopping-error"
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
        can: "boîte",
        unknown: "inconnue"
    };

    return labels[unit] ?? unit;
}


function formatQuantity(
    quantity,
    unit
) {
    if (
        quantity === null ||
        quantity === undefined
    ) {
        return "quantité inconnue";
    }

    return `${quantity} ${unitLabel(unit)}`;
}


function storageKey() {
    return (
        "fridge-agent-shopping:" +
        currentPlanId
    );
}


function itemKey(item) {
    return [
        item.status,
        item.name,
        item.required_quantity,
        item.unit
    ].join("|");
}


function loadCheckedItems() {
    checkedItems = new Set();

    try {
        const stored =
            JSON.parse(
                localStorage.getItem(
                    storageKey()
                ) ?? "[]"
            );

        checkedItems =
            new Set(stored);

    } catch (error) {
        console.warn(
            "Invalid shopping state",
            error
        );
    }
}


function saveCheckedItems() {
    localStorage.setItem(
        storageKey(),
        JSON.stringify(
            [...checkedItems]
        )
    );
}


function createShoppingRow(
    item
) {
    const key =
        itemKey(item);

    const label =
        document.createElement(
            "label"
        );

    label.className =
        "shopping-item";

    if (checkedItems.has(key)) {
        label.classList.add(
            "completed"
        );
    }

    const checkbox =
        document.createElement(
            "input"
        );

    checkbox.type =
        "checkbox";

    checkbox.checked =
        checkedItems.has(key);

    const content =
        document.createElement(
            "div"
        );

    content.className =
        "shopping-item-content";

    const name =
        document.createElement(
            "strong"
        );

    name.textContent =
        item.name;

    const detail =
        document.createElement(
            "span"
        );

    if (
        item.status === "buy"
    ) {
        detail.textContent =
            "Acheter " +
            formatQuantity(
                item.quantity_to_buy,
                item.quantity_to_buy_unit
            );

    } else {
        detail.textContent =
            "Besoin : " +
            formatQuantity(
                item.required_quantity,
                item.unit
            );
    }

    content.append(
        name,
        detail
    );

    if (
        item.status ===
        "check_inventory"
    ) {
        const inventory =
            document.createElement(
                "small"
            );

        inventory.className =
            "shopping-inventory-note";

        const descriptions =
            item.inventory.map(
                entry => {
                    const source =
                        entry.source === "fridge"
                            ? "frigo"
                            : "placard";

                    return (
                        `${source}: ` +
                        formatQuantity(
                            entry.quantity,
                            entry.unit
                        )
                    );
                }
            );

        inventory.textContent =
            "Stock détecté — " +
            descriptions.join(", ");

        content.appendChild(
            inventory
        );
    }

    checkbox.addEventListener(
        "change",
        () => {
            if (checkbox.checked) {
                checkedItems.add(key);
                label.classList.add(
                    "completed"
                );

            } else {
                checkedItems.delete(key);
                label.classList.remove(
                    "completed"
                );
            }

            saveCheckedItems();
            updateProgress();
        }
    );

    label.append(
        checkbox,
        content
    );

    return label;
}


function renderShopping() {
    const buyItems =
        shoppingData.items.filter(
            item =>
                item.status === "buy"
        );

    const checkItems =
        shoppingData.items.filter(
            item =>
                item.status ===
                "check_inventory"
        );

    document.getElementById(
        "shopping-buy-count"
    ).textContent =
        buyItems.length;

    document.getElementById(
        "shopping-check-count"
    ).textContent =
        checkItems.length;

    document.getElementById(
        "shopping-covered-count"
    ).textContent =
        shoppingData
            .covered_items.length;

    document.getElementById(
        "covered-summary-count"
    ).textContent =
        shoppingData
            .covered_items.length;

    const buyContainer =
        document.getElementById(
            "buy-items"
        );

    const checkContainer =
        document.getElementById(
            "check-items"
        );

    const coveredContainer =
        document.getElementById(
            "covered-items"
        );

    buyContainer.innerHTML = "";
    checkContainer.innerHTML = "";
    coveredContainer.innerHTML = "";

    for (const item of buyItems) {
        buyContainer.appendChild(
            createShoppingRow(item)
        );
    }

    for (const item of checkItems) {
        checkContainer.appendChild(
            createShoppingRow(item)
        );
    }

    document.getElementById(
        "buy-section"
    ).hidden =
        buyItems.length === 0;

    document.getElementById(
        "check-section"
    ).hidden =
        checkItems.length === 0;

    for (
        const item
        of shoppingData.covered_items
    ) {
        const row =
            document.createElement(
                "div"
            );

        row.className =
            "covered-item";

        const name =
            document.createElement(
                "span"
            );

        name.textContent =
            item.name;

        const quantity =
            document.createElement(
                "strong"
            );

        quantity.textContent =
            formatQuantity(
                item.required_quantity,
                item.unit
            );

        row.append(
            name,
            quantity
        );

        coveredContainer.appendChild(
            row
        );
    }

    updateProgress();
}


function updateProgress() {
    if (!shoppingData) {
        return;
    }

    const actionable =
        shoppingData.items;

    const validKeys =
        new Set(
            actionable.map(itemKey)
        );

    let completed = 0;

    for (const key of checkedItems) {
        if (validKeys.has(key)) {
            completed += 1;
        }
    }

    const total =
        actionable.length;

    document.getElementById(
        "shopping-progress"
    ).textContent =
        total === 0
            ? "Rien à acheter."
            : `${completed} sur ${total} éléments traités`;
}


async function resolvePlanId() {
    const parameters =
        new URLSearchParams(
            window.location.search
        );

    const requested =
        parameters.get("plan");

    if (requested) {
        return requested;
    }

    const latest =
        await fetchJson(
            "/api/meal-plans/latest"
        );

    return latest.id;
}


async function loadShopping() {
    errorElement.hidden = true;

    try {
        currentPlanId =
            await resolvePlanId();

        shoppingData =
            await fetchJson(
                `/api/meal-plans/` +
                `${currentPlanId}/shopping-list`
            );

        loadCheckedItems();

        loadingElement.hidden =
            true;

        emptyElement.hidden =
            true;

        contentElement.hidden =
            false;

        renderShopping();

    } catch (error) {
        console.error(error);

        loadingElement.hidden =
            true;

        if (error.status === 404) {
            emptyElement.hidden =
                false;

            contentElement.hidden =
                true;

            return;
        }

        errorElement.textContent =
            "Impossible de charger la liste de courses.";

        errorElement.hidden =
            false;
    }
}


document.getElementById(
    "reset-shopping"
).addEventListener(
    "click",
    () => {
        checkedItems.clear();
        saveCheckedItems();
        renderShopping();
    }
);


loadShopping();