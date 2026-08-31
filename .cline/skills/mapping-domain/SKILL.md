# Mapping Domain

Source of truth for Mapping-specific business rules.

## Contexts

- Import Categories
- Import Attributes
- Import Values
- Import Review
- Rozetka Categories
- Rozetka Attributes
- Rozetka Attribute Values

## Core Rules

- Mapping contexts are independent.
- Never infer filters or fields from another mapping context.
- Never reuse mapping-specific state across contexts.
- Internal and external entities are separate dimensions.
- Reusable UI primitives are allowed; reusable domain-specific filter state is discouraged.
- Do not add a filter to another context because it exists in a similar tab.

## Filter Matrix

| Filter | RZ Categories | RZ Attributes | RZ Values | Import |
|---|---:|---:|---:|---:|
| Internal Category | ✅ | ✅ | ✅ | per existing implementation |
| Parent Category | ✅ | ✅ | ✅ | per existing implementation |
| Rozetka Category | ✅ | ✅ | ✅ | ❌ |
| Internal Attribute | ❌ | ✅ | ✅ | per existing implementation |
| Rozetka Attribute | ❌ | ✅ | ✅ | ❌ |
| Internal Value | ❌ | ❌ | ✅ | per existing implementation |
| Rozetka Value | ❌ | ❌ | ✅ | ❌ |

## Search Rules

- Internal and external search must be independent.
- Do not use a generic `q` when separate search dimensions are required.
- Verify API parameter semantics before changing search behavior.

## State Rules

Each tab owns its own:
- filters
- search
- pagination
- sorting
- reset
- API query state

One tab must never mutate another tab's state.

## API Rules

API parameters must match the exact mapping context.

Do not send attribute-specific parameters to Category Mapping.
Do not send value-specific parameters to Category or Attribute Mapping.
Do not send Rozetka-specific parameters to Import Mapping.

## Adding a Filter

Before adding a filter:
1. Identify its mapping context.
2. Identify the entity it filters.
3. Check this matrix.
4. Check backend support.
5. Add it only to the correct context.

When uncertain, do not guess.

## Completion

Before reporting completion, verify:
- correct filters
- correct context
- independent state
- correct API parameters
- no cross-context leakage