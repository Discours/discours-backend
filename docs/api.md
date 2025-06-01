

## API Documentation

### GraphQL Schema
- Mutations: Authentication, content management, security
- Queries: Content retrieval, user data
- Types: Author, Topic, Shout, Community

### Key Features

#### Security Management
- Password change with validation
- Email change with confirmation
- Two-factor authentication flow
- Protected fields for user privacy

#### Content Management
- Publication system with drafts
- Topic and community organization
- Author collaboration tools
- Real-time notifications

#### Following System
- Subscribe to authors and topics
- Cache-optimized operations
- Consistent UI state management

## Database

### Models
- `Author` - User accounts with RBAC
- `Shout` - Publications and articles
- `Topic` - Content categorization
- `Community` - User groups

### Cache System
- Redis-based caching
- Automatic cache invalidation
- Optimized for real-time updates
