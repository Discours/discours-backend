# Following System

## Overview
System supports following different entity types:
- Authors
- Topics
- Communities
- Shouts (Posts)

## GraphQL API

### Mutations

#### follow
Follow an entity (author/topic/community/shout).

**Parameters:**
- `what: String!` - Entity type (`AUTHOR`, `TOPIC`, `COMMUNITY`, `SHOUT`)
- `slug: String` - Entity slug
- `entity_id: Int` - Optional entity ID

**Returns:**
```typescript
{
  authors?: Author[]        // For AUTHOR type
  topics?: Topic[]          // For TOPIC type
  communities?: Community[] // For COMMUNITY type
  shouts?: Shout[]          // For SHOUT type
  error?: String            // Error message if any
}
```

#### unfollow
Unfollow an entity.

**Parameters:** Same as `follow`

**Returns:** Same as `follow`

**Important:** Always returns current following list even if the subscription was not found, ensuring UI consistency.

### Queries

#### get_shout_followers
Get list of users who reacted to a shout.

**Parameters:**
- `slug: String` - Shout slug
- `shout_id: Int` - Optional shout ID

**Returns:**
```typescript
Author[] // List of authors who reacted
```

## Caching System

### Supported Entity Types
- Authors: `cache_author`, `get_cached_follower_authors`
- Topics: `cache_topic`, `get_cached_follower_topics`
- Communities: No cache
- Shouts: No cache

### Cache Flow
1. On follow/unfollow:
   - Update entity in cache
   - **Invalidate user's following list cache** (NEW)
   - Update follower's following list
2. Cache is updated before notifications

### Cache Invalidation (NEW)
Following cache keys are invalidated after operations:
- `author:follows-topics:{user_id}` - After topic follow/unfollow
- `author:follows-authors:{user_id}` - After author follow/unfollow

This ensures fresh data is fetched from database on next request.

## Error Handling

### Enhanced Error Handling (UPDATED)
- Unauthorized access check
- Entity existence validation
- Duplicate follow prevention
- **Graceful handling of "following not found" errors**
- **Always returns current following list, even on errors**
- Full error logging
- Transaction safety with `local_session()`

### Error Response Format
```typescript
{
  error?: "following was not found" | "invalid unfollow type" | "access denied",
  topics?: Topic[],     // Always present for topic operations
  authors?: Author[],   // Always present for author operations
  // ... other entity types
}
```

## Recent Fixes (NEW)

### Issue: Stale UI State on Unfollow Errors
**Problem:** When unfollow operation failed with "following was not found", the client didn't update its state because it only processed successful responses.

**Root Cause:**
1. `unfollow` mutation returned error with empty follows list `[]`
2. Client logic: `if (result && !result.error)` prevented state updates on errors
3. User remained "subscribed" in UI despite no actual subscription in database

**Solution:**
1. **Always fetch current following list** from cache/database
2. **Return actual following state** even when subscription not found
3. **Add cache invalidation** after successful operations
4. **Enhanced logging** for debugging

### Code Changes
```python
# Before (BROKEN)
if sub:
    # ... process unfollow
else:
    return {"error": "following was not found", f"{entity_type}s": follows}  # follows was []

# After (FIXED)  
if sub:
    # ... process unfollow
    # Invalidate cache
    await redis.execute("DEL", f"author:follows-{entity_type}s:{follower_id}")
else:
    error = "following was not found"

# Always get current state
existing_follows = await get_cached_follows_method(follower_id)
return {f"{entity_type}s": existing_follows, "error": error}
```

## Notifications

- Sent when author is followed/unfollowed
- Contains:
  - Follower info
  - Author ID
  - Action type ("follow"/"unfollow")

## Database Schema

### Follower Tables
- `AuthorFollower`
- `TopicFollower`
- `CommunityFollower`
- `ShoutReactionsFollower`

Each table contains:
- `follower` - ID of following user
- `{entity_type}` - ID of followed entity

## Testing

Run the test script to verify fixes:
```bash
python test_unfollow_fix.py
```

### Test Coverage
- ✅ Unfollow existing subscription
- ✅ Unfollow non-existent subscription  
- ✅ Cache invalidation
- ✅ Proper error handling
- ✅ UI state consistency 