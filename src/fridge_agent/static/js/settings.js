let likedFoods = [];
let avoidedFoods = [];
let settingsDirty = false;


const form =
    document.getElementById("settings-form");

const errorElement =
    document.getElementById("settings-error");

const successElement =
    document.getElementById("settings-success");

const dirtyElement =
    document.getElementById("settings-dirty");

const saveButton =
    document.getElementById("save-settings");


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


function setDirty(value) {
    settingsDirty = value;
    dirtyElement.hidden = !value;
}


function normalizeTag(value) {
    return value
        .trim()
        .replace(/\s+/g, " ");
}


function addUniqueTag(
    collection,
    value
) {
    value = normalizeTag(value);

    if (!value) {
        return false;
    }

    const exists =
        collection.some(
            item =>
                item.localeCompare(
                    value,
                    undefined,
                    {
                        sensitivity: "accent"
                    }
                ) === 0
        );

    if (exists) {
        return false;
    }

    collection.push(value);

    return true;
}


function renderTags(
    containerId,
    collection,
    type
) {
    const container =
        document.getElementById(
            containerId
        );

    container.innerHTML = "";

    if (collection.length === 0) {
        const empty =
            document.createElement(
                "span"
            );

        empty.className =
            "tag-empty";

        empty.textContent =
            "Aucun élément";

        container.appendChild(
            empty
        );

        return;
    }

    collection.forEach(
        (value, index) => {
            const tag =
                document.createElement(
                    "span"
                );

            tag.className =
                type === "avoid"
                    ? "tag tag-avoid"
                    : "tag";

            const text =
                document.createElement(
                    "span"
                );

            text.textContent =
                value;

            const button =
                document.createElement(
                    "button"
                );

            button.type =
                "button";

            button.textContent =
                "×";

            button.title =
                "Supprimer";

            button.addEventListener(
                "click",
                () => {
                    collection.splice(
                        index,
                        1
                    );

                    renderPreferences();
                    setDirty(true);
                    hideMessages();
                }
            );

            tag.append(
                text,
                button
            );

            container.appendChild(
                tag
            );
        }
    );
}


function renderPreferences() {
    renderTags(
        "liked-foods",
        likedFoods,
        "like"
    );

    renderTags(
        "avoided-foods",
        avoidedFoods,
        "avoid"
    );
}


function addTagFromInput(
    inputId,
    collection
) {
    const input =
        document.getElementById(
            inputId
        );

    if (
        addUniqueTag(
            collection,
            input.value
        )
    ) {
        input.value = "";

        renderPreferences();
        setDirty(true);
        hideMessages();
    }

    input.focus();
}


document
    .getElementById(
        "add-liked-food"
    )
    .addEventListener(
        "click",
        () => {
            addTagFromInput(
                "liked-food-input",
                likedFoods
            );
        }
    );


document
    .getElementById(
        "add-avoided-food"
    )
    .addEventListener(
        "click",
        () => {
            addTagFromInput(
                "avoided-food-input",
                avoidedFoods
            );
        }
    );


for (const [
    inputId,
    collection
] of [
    [
        "liked-food-input",
        likedFoods
    ],
    [
        "avoided-food-input",
        avoidedFoods
    ]
]) {
    document
        .getElementById(
            inputId
        )
        .addEventListener(
            "keydown",
            event => {
                if (
                    event.key !==
                    "Enter"
                ) {
                    return;
                }

                event.preventDefault();

                addTagFromInput(
                    inputId,
                    collection
                );
            }
        );
}


async function loadSettings() {
    hideMessages();

    try {
        const settings =
            await fetchJson(
                "/api/settings"
            );

        document.getElementById(
            "people"
        ).value =
            settings.people;

        document.getElementById(
            "planning-days"
        ).value =
            settings.planning_days;

        document.getElementById(
            "plan-lunch"
        ).checked =
            settings.plan_lunch;

        document.getElementById(
            "plan-dinner"
        ).checked =
            settings.plan_dinner;

        document.getElementById(
            "weekday-time"
        ).value =
            settings
                .weekday_max_cooking_minutes;

        document.getElementById(
            "weekend-time"
        ).value =
            settings
                .weekend_max_cooking_minutes;

        document.getElementById(
            "use-leftovers"
        ).checked =
            settings.use_leftovers;

        document.getElementById(
            "settings-notes"
        ).value =
            settings.notes ?? "";

        likedFoods = [
            ...settings.liked_foods
        ];

        avoidedFoods = [
            ...settings.avoided_foods
        ];

        renderPreferences();
        setDirty(false);

    } catch (error) {
        console.error(error);

        errorElement.textContent =
            "Impossible de charger les paramètres.";

        errorElement.hidden =
            false;
    }
}


form.addEventListener(
    "input",
    event => {
        if (
            event.target.closest(
                ".tag-input-row"
            )
        ) {
            return;
        }

        setDirty(true);
        hideMessages();
    }
);


form.addEventListener(
    "change",
    () => {
        setDirty(true);
        hideMessages();
    }
);


form.addEventListener(
    "submit",
    async event => {
        event.preventDefault();

        hideMessages();

        const planLunch =
            document.getElementById(
                "plan-lunch"
            ).checked;

        const planDinner =
            document.getElementById(
                "plan-dinner"
            ).checked;

        if (
            !planLunch &&
            !planDinner
        ) {
            errorElement.textContent =
                "Activez au moins un type de repas : déjeuner ou dîner.";

            errorElement.hidden =
                false;

            return;
        }

        const payload = {
            people:
                Number(
                    document.getElementById(
                        "people"
                    ).value
                ),

            planning_days:
                Number(
                    document.getElementById(
                        "planning-days"
                    ).value
                ),

            plan_lunch:
                planLunch,

            plan_dinner:
                planDinner,

            weekday_max_cooking_minutes:
                Number(
                    document.getElementById(
                        "weekday-time"
                    ).value
                ),

            weekend_max_cooking_minutes:
                Number(
                    document.getElementById(
                        "weekend-time"
                    ).value
                ),

            use_leftovers:
                document.getElementById(
                    "use-leftovers"
                ).checked,

            liked_foods:
                likedFoods,

            avoided_foods:
                avoidedFoods,

            notes:
                document.getElementById(
                    "settings-notes"
                ).value.trim()
        };

        saveButton.disabled =
            true;

        try {
            await fetchJson(
                "/api/settings",
                {
                    method: "PUT",
                    headers: {
                        "Content-Type":
                            "application/json"
                    },
                    body:
                        JSON.stringify(
                            payload
                        )
                }
            );

            successElement.textContent =
                "Paramètres enregistrés.";

            successElement.hidden =
                false;

            setDirty(false);

        } catch (error) {
            console.error(error);

            errorElement.textContent =
                `Impossible d'enregistrer : ${error.message}`;

            errorElement.hidden =
                false;

        } finally {
            saveButton.disabled =
                false;
        }
    }
);


window.addEventListener(
    "beforeunload",
    event => {
        if (!settingsDirty) {
            return;
        }

        event.preventDefault();
        event.returnValue = "";
    }
);


loadSettings();