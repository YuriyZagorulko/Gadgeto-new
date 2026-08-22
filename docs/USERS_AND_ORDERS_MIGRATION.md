# Users and Orders Migration Assessment

## Users

| Metric | Value |
|---|---|
| WP users | 5 |
| Admin | 1 (GadgetoMaster) |
| Customers | 4 (test accounts) |

### Migration Decision: DO NOT MIGRATE

Reasons:
1. Only 5 users, 4 are test accounts
2. Passwords use WP hashing (phpass) - incompatible with bcrypt
3. No meaningful user data to preserve
4. Cleaner to create fresh accounts when needed
5. Admin account will be created manually during seeding

### Recommended Approach
- Create 1 admin account manually during deployment
- Email verification for new users
- No legacy user migration

## Orders

| Metric | Value |
|---|---|
| HPOS orders | 12 |
| Non-trash orders | 2 (test orders) |
| Order items | 33 |
| Total orders | 11-12 rows |

### Migration Decision: DO NOT AUTOMATICALLY MIGRATE

Reasons:
1. Only 12 orders, 10 are trash/test
2. 2 non-trash orders are test data (~70 UAH each)
3. No real order history to preserve
4. Orders reference WP user IDs (would need mapping)
5. Payment references are plugin-specific (mrkv_liqpay)

### Recommended Approach
- Archive order data as JSON reference (not migrated to PostgreSQL)
- Create audit log of historical orders in a separate archive table if needed
- New system starts with clean order history

## Security Considerations

- WP password hashes cannot be migrated (incompatible algorithm)
- LiqPay payment references are time-limited
- NP shipping references are snapshotted per order
- No PII concerns (all test data)

## Conclusion

Users and orders should NOT be migrated automatically. The data volume is negligible (5 users, 11 orders) and migrating them would introduce unnecessary complexity. New users will register fresh, and the first real orders will be created in the new system.
