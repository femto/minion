# Code Review Skill - Examples

## Example 1: Security Review

### Input Code (Python)
```python
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    result = db.execute(query)
    return result
```

### Review Output
```markdown
## Code Review Summary

**Severity: CRITICAL**

### Issues Found

#### 1. SQL Injection Vulnerability (Critical)
- **File**: auth.py:2
- **Category**: Security
- **Issue**: User input is directly interpolated into SQL query, allowing SQL injection attacks.
- **Suggested Fix**:
```python
def login(username, password):
    query = "SELECT * FROM users WHERE username=? AND password=?"
    result = db.execute(query, (username, password))
    return result
```

#### 2. Plain Text Password Comparison (Critical)
- **File**: auth.py:2
- **Category**: Security
- **Issue**: Passwords appear to be stored and compared in plain text.
- **Suggested Fix**: Use password hashing (bcrypt, argon2)
```python
import bcrypt

def login(username, password):
    query = "SELECT * FROM users WHERE username=?"
    user = db.execute(query, (username,)).fetchone()
    if user and bcrypt.checkpw(password.encode(), user['password_hash']):
        return user
    return None
```
```

## Example 2: Performance Review

### Input Code (JavaScript)
```javascript
async function getOrdersWithProducts(userId) {
    const orders = await db.query('SELECT * FROM orders WHERE user_id = ?', [userId]);

    for (const order of orders) {
        order.products = await db.query(
            'SELECT * FROM products WHERE order_id = ?',
            [order.id]
        );
    }

    return orders;
}
```

### Review Output
```markdown
## Code Review Summary

**Severity: HIGH**

### Issues Found

#### 1. N+1 Query Problem (High)
- **File**: orders.js:3-8
- **Category**: Performance
- **Issue**: For each order, a separate query is made to fetch products. With 100 orders, this results in 101 database queries.
- **Suggested Fix**: Use JOIN or batch loading
```javascript
async function getOrdersWithProducts(userId) {
    const query = `
        SELECT o.*, p.*
        FROM orders o
        LEFT JOIN order_products op ON o.id = op.order_id
        LEFT JOIN products p ON op.product_id = p.id
        WHERE o.user_id = ?
    `;
    const results = await db.query(query, [userId]);

    // Group products by order
    const ordersMap = new Map();
    for (const row of results) {
        if (!ordersMap.has(row.order_id)) {
            ordersMap.set(row.order_id, { ...row, products: [] });
        }
        if (row.product_id) {
            ordersMap.get(row.order_id).products.push(row);
        }
    }

    return Array.from(ordersMap.values());
}
```

### Positive Aspects
- Proper use of parameterized queries
- Async/await pattern correctly implemented
```

## Example 3: Code Quality Review

### Input Code (Python)
```python
def p(d, t):
    r = []
    for i in d:
        if i['type'] == t:
            x = {}
            x['name'] = i['name']
            x['value'] = i['value']
            if i['active'] == True:
                x['status'] = 'active'
            else:
                x['status'] = 'inactive'
            r.append(x)
    return r
```

### Review Output
```markdown
## Code Review Summary

**Severity: MEDIUM**

### Issues Found

#### 1. Poor Variable Naming (Medium)
- **File**: processor.py:1
- **Category**: Code Quality
- **Issue**: Single-letter variable names (p, d, t, r, i, x) make code unreadable.
- **Suggested Fix**:
```python
def filter_items_by_type(items, item_type):
    filtered_items = []
    for item in items:
        if item['type'] == item_type:
            filtered_item = {
                'name': item['name'],
                'value': item['value'],
                'status': 'active' if item['active'] else 'inactive'
            }
            filtered_items.append(filtered_item)
    return filtered_items
```

#### 2. Comparison to True (Low)
- **File**: processor.py:8
- **Category**: Code Quality
- **Issue**: `if i['active'] == True` should be `if i['active']`

#### 3. Missing Type Hints (Low)
- **File**: processor.py:1
- **Category**: Code Quality
- **Suggested Fix**:
```python
from typing import List, Dict, Any

def filter_items_by_type(
    items: List[Dict[str, Any]],
    item_type: str
) -> List[Dict[str, Any]]:
    ...
```

### Positive Aspects
- Function performs a single, focused task
- No external dependencies
```

## Example 4: Full Pull Request Review

### PR Description
"Added user profile update functionality"

### Review Output
```markdown
## Pull Request Review: User Profile Update

**Overall Assessment: APPROVED with suggestions**
**Severity: Medium (no blockers)**

### Summary
The PR implements user profile update functionality. The implementation is generally solid but has a few areas for improvement.

### Files Changed
- `api/users.py` (+45, -2)
- `models/user.py` (+12, -0)
- `tests/test_users.py` (+30, -0)

### Issues Found

#### api/users.py

**Line 23 - Input Validation (Medium)**
```python
# Current
def update_profile(user_id, data):
    user = User.get(user_id)
    user.update(data)
```
```python
# Suggested
def update_profile(user_id: int, data: dict):
    allowed_fields = {'name', 'email', 'bio'}
    filtered_data = {k: v for k, v in data.items() if k in allowed_fields}

    if not filtered_data:
        raise ValueError("No valid fields to update")

    user = User.get(user_id)
    if not user:
        raise NotFoundError(f"User {user_id} not found")

    user.update(filtered_data)
```

**Line 35 - Missing Authorization Check (High)**
- Issue: No verification that the requesting user owns this profile
- Suggested: Add authorization middleware or check

### Positive Aspects
- Good test coverage for happy path
- Clean separation of concerns
- Follows existing code patterns

### Recommendations (Priority Order)
1. **High**: Add authorization check before allowing profile updates
2. **Medium**: Implement input validation/sanitization
3. **Low**: Add error handling for database failures
4. **Low**: Consider adding audit logging for profile changes

### Test Coverage
- Happy path: ✅ Covered
- Invalid user ID: ❌ Missing
- Unauthorized access: ❌ Missing
- Invalid input data: ❌ Missing
```

## Common Review Patterns

### Security Patterns to Flag
```python
# Bad: Command injection
os.system(f"process {user_input}")

# Bad: Path traversal
file_path = f"/data/{user_input}"
open(file_path)

# Bad: Hardcoded secrets
API_KEY = "sk-1234567890"

# Bad: Insecure random
import random
token = random.randint(0, 999999)
```

### Performance Patterns to Flag
```python
# Bad: String concatenation in loop
result = ""
for item in items:
    result += str(item)

# Bad: Repeated function calls
for i in range(len(items)):  # len() called each iteration

# Bad: Not using generators for large data
data = [process(x) for x in huge_list]  # Creates full list in memory
```

### Code Quality Patterns to Flag
```python
# Bad: Deep nesting
if a:
    if b:
        if c:
            if d:
                do_something()

# Bad: Long function
def do_everything():
    # 200+ lines of code
    pass

# Bad: Magic numbers
if status == 3:  # What is 3?
    process()
```
