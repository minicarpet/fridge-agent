# fridge-agent
an AI agent which provide recipes

## Favorite cuisines

Save preferred cuisines (for example Asian, Mexican or Thai) as tags in
**Settings → Cuisines favorites**, using **Ajouter** or Enter for each cuisine.
These preferences are stored locally and
passed to the AI meal planner alongside liked foods, avoided foods, household
settings and inventory.

The menu page prefills **Cuisines pour ce menu** with your saved favorites.
Edit the comma-separated list for that menu only, or clear it to generate
without a cuisine preference. These changes do not update your saved settings.
Cuisine preferences guide recipe selection without overriding avoided foods,
cooking-time limits or the priority given to available ingredients.

API clients can send `{"favorite_cuisines": ["Asian", "Thai"]}` in the JSON body
of `POST /api/meal-plans/generate?start_date=YYYY-MM-DD`. Omitting the body or
the field (or using `null`) uses saved favorites; an empty list disables cuisine
preferences for that request. `GET /api/settings` and `PUT /api/settings` expose
the saved `favorite_cuisines` list.
Omitting `favorite_cuisines` when updating settings preserves the saved list;
sending an empty list clears it.

Run the preference integration tests without live AI calls:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
