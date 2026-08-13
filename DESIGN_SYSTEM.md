# Baysoko Design System Reference

## 1. Overview
This document outlines the design principles, patterns, and standards used across Baysoko Marketplace templates. The system is based on a vibrant, modern e-commerce aesthetic with strong visual hierarchy and user-friendly interactions.

## 2. Core Design Principles

### 2.1 Visual Hierarchy
- **Primary Actions**: Use `--primary` (#FF6B35) for primary CTAs
- **Secondary Actions**: Use `--secondary` (#FFD166) for secondary actions
- **Accent Elements**: Use `--accent` (#06D6A0) for highlights and success states
- **Information**: Use `--info` (#118AB2) for informational elements
- **Warning/Danger**: Use `--warning` (#FF9E1F) and `--danger` (#EF476F) appropriately

### 2.2 Spacing System
```css
--spacing-xs: 0.5rem;   /* 8px */
--spacing-sm: 1rem;     /* 16px */
--spacing-md: 1.5rem;   /* 24px */
--spacing-lg: 2rem;     /* 32px */
--spacing-xl: 3rem;     /* 48px */
--spacing-xxl: 4rem;    /* 64px */
```

### 2.3 Typography
- **Headings**: 'Outfit', sans-serif (bold weights: 700-900)
- **Body**: 'Plus Jakarta Sans', sans-serif (weights: 300-800)
- **Base Size**: 16px (responsive down to 13px on mobile)

### 2.4 Border Radius
```css
--radius-sm: 8px;    /* Small elements */
--radius-md: 12px;   /* Cards, buttons */
--radius-lg: 16px;   /* Large containers */
--radius-xl: 20px;   /* Hero sections */
--radius-full: 50%;  /* Circular elements */
```

## 3. Component Standards

### 3.1 Buttons
```html
<!-- Primary Button -->
<button class="btn-custom btn-primary">
  <i class="bi bi-icon-name"></i>
  Button Text
</button>

<!-- Secondary Button -->
<button class="btn-custom btn-secondary">
  <i class="bi bi-icon-name"></i>
  Button Text
</button>

<!-- Ghost Button -->
<button class="btn-custom btn-ghost">
  <i class="bi bi-icon-name"></i>
  Button Text
</button>
```

**Characteristics:**
- Minimum height: 44px
- Padding: var(--spacing-sm) var(--spacing-lg)
- Border radius: var(--radius-md)
- Include icons where appropriate
- Hover effects with transform and shadow changes
- Loading states with spinner icons

### 3.2 Cards
```html
<div class="card-custom">
  <div class="card-header">Title</div>
  <div class="card-body">Content</div>
</div>
```

**Characteristics:**
- Background: var(--card-bg)
- Border: 1px solid var(--border-color)
- Border radius: var(--radius-lg)
- Shadow: var(--shadow-sm)
- Hover: translateY(-5px) + var(--shadow-lg)
- Padding: var(--spacing-lg)

### 3.3 Forms
```html
<div class="form-group">
  <label class="form-label required-field">Field Name</label>
  <input type="text" class="form-control" placeholder="Placeholder">
  <div class="field-help">Helper text</div>
  <div class="error-message">
    <i class="bi bi-exclamation-circle"></i>
    Error message
  </div>
</div>
```

**Field Types:**
- **Text inputs**: Full border, rounded corners
- **Select dropdowns**: Match input styling with custom arrow
- **Checkboxes/Radios**: Custom styling with icons
- **Textareas**: Resizable vertical only

**Validation States:**
- **Valid**: Green border (success state)
- **Invalid**: Red border with error message
- **Required**: Asterisk (*) after label

### 3.4 Navigation Elements
**Top Navigation:**
- Fixed position
- Height: 70px (60px mobile)
- Blur background effect
- Search bar centered on desktop, toggle on mobile

**Side Navigation:**
- Fixed left position
- Width: 80px collapsed, 320px expanded
- Icons with text labels on expansion
- Active state with background color

**Bottom Navigation (Mobile):**
- Fixed bottom position
- 5 main actions
- Icons with labels
- Notification badges

### 3.5 Sections
```html
<section class="horizontal-scroll-section scroll-animate">
  <div class="container-custom">
    <div class="section-header">
      <h2 class="section-title">Section Title</h2>
      <p class="section-subtitle">Section description</p>
    </div>
    <div class="scroll-container">
      <!-- Scrollable content -->
    </div>
  </div>
</section>
```

**Section Types:**
- **Hero Sections**: Full viewport height with gradient backgrounds
- **Horizontal Scroll**: Scrollable content with custom arrows
- **Standard Sections**: Content with title and subtitle
- **Ad Sections**: Full-width promotional banners

## 4. Color Usage Guidelines

### 4.1 Backgrounds
- **Primary Background**: var(--bg-primary)
- **Secondary Background**: var(--bg-secondary) (for section backgrounds)
- **Card Background**: var(--card-bg)
- **Gradient Backgrounds**: Use for hero sections and highlights

### 4.2 Text Colors
- **Primary Text**: var(--text-primary) for main content
- **Secondary Text**: var(--text-secondary) for descriptions
- **Tertiary Text**: var(--text-tertiary) for metadata
- **White Text**: On dark/gradient backgrounds

### 4.3 Borders
- **Default**: var(--border-color)
- **Focus/Hover**: var(--primary)
- **Error**: #EF476F (danger color)

## 5. Animation Standards

### 5.1 Transitions
```css
--transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
--transition-fast: all 0.15s ease-out;
--transition-slow: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
```

**Usage:**
- **Hover effects**: var(--transition)
- **Fast interactions**: var(--transition-fast)
- **Page transitions**: var(--transition-slow)

### 5.2 Keyframe Animations
```css
/* Fade in from directions */
.animate-fade-up, .animate-fade-down, .animate-fade-left, .animate-fade-right

/* Scale in */
.animate-scale-in

/* Floating elements */
.floating (with animation-delay based on index)
```

### 5.3 Scroll Animations
```css
.scroll-animate {
  opacity: 0;
  transform: translateY(30px);
  transition: all 0.8s cubic-bezier(0.4, 0, 0.2, 1);
}

.scroll-animate.animated {
  opacity: 1;
  transform: translateY(0);
}
```

## 6. Responsive Design Rules

### 6.1 Breakpoints
```css
/* Large desktop: 1200px+ (default) */

/* Tablet: 768px - 1199px */
@media (max-width: 768px) {
  /* Adjustments */
}

/* Mobile: 576px - 767px */
@media (max-width: 576px) {
  /* Mobile optimizations */
}

/* Small mobile: 350px - 575px */
@media (max-width: 350px) {
  /* Minimum viable adjustments */
}
```

### 6.2 Responsive Patterns
1. **Desktop**: Full navigation, side menu optional
2. **Tablet**: Simplified navigation, hidden side menu
3. **Mobile**: Bottom navigation, hamburger menu
4. **Small Mobile**: Reduced font sizes, tighter spacing

### 6.3 Mobile-First Considerations
- Minimum tap target: 44px × 44px
- Font size never below 13px
- Avoid horizontal scrolling in main content
- Stack elements vertically on small screens

## 7. Icon Usage
- **Bootstrap Icons** as primary icon set
- **Size standards**: 
  - Small: 1rem
  - Medium: 1.3rem
  - Large: 2rem
  - Extra Large: 3rem
- **Color**: Inherit text color or use brand colors
- **Spacing**: Gap of var(--spacing-xs) between icon and text

## 8. Image Handling
- **Aspect ratios**: Maintain consistent ratios
- **Object fit**: `cover` for featured images
- **Loading**: Lazy loading for below-fold images
- **Fallbacks**: Placeholder images on error
- **Optimization**: WebP format preferred

## 9. Form-Specific Guidelines

### 9.1 Form Layout
- Use `.form-grid` for multi-column layouts
- `.full-width` for elements spanning multiple columns
- Section headers with icons and descriptions
- Progress indicators for multi-step forms

### 9.2 File Uploads
- Drag-and-drop zones with clear visual feedback
- Preview thumbnails for uploaded images
- File size and format validation
- Remove/Replace functionality

### 9.3 Character Counters
- Visible for text fields with limits
- Color coding (normal/warning/error)
- Real-time updates

## 10. JavaScript Integration

### 10.1 Event Handling
- Use `data-` attributes for behavior
- Progressive enhancement
- Loading states for async operations
- Error states with user-friendly messages

### 10.2 Dynamic Content
- Smooth animations for content changes
- Lazy loading for performance
- Infinite scroll with loading indicators
- Real-time updates with subtle notifications

## 11. Accessibility Standards

### 11.1 Semantic HTML
- Proper heading hierarchy (h1-h6)
- ARIA labels for interactive elements
- Form field labels and associations
- Keyboard navigation support

### 11.2 Color Contrast
- Minimum 4.5:1 for normal text
- Minimum 3:1 for large text
- Use color alone for status indicators

### 11.3 Focus Management
- Visible focus indicators
- Logical tab order
- Skip navigation links
- Focus trapping for modals

## 12. Implementation Examples

### 12.1 Creating a New Component
1. Use existing CSS variables
2. Follow spacing system
3. Include hover/focus states
4. Add responsive behavior
5. Test with screen readers

### 12.2 Modifying Existing Components
1. Check design system reference
2. Maintain consistency
3. Update documentation
4. Test across breakpoints

### 12.3 Adding New Pages
1. Use base.html template
2. Follow section patterns
3. Implement scroll animations
4. Ensure mobile responsiveness

## 13. File Structure Convention
```
templates/
├── base.html              # Base template with design system
├── home.html             # Home page (reference implementation)
├── listings/
│   ├── listing_form.html # Standard form template
│   ├── listing_form_ai.html # AI-enhanced form
│   └── ...              # Other listing templates
├── storefront/
│   └── ...              # Store-related templates
└── includes/            # Reusable components
```

## 14. Theme Support
The design system supports both light and dark themes using CSS custom properties. All color references should use CSS variables, not hard-coded values.

## 15. Quality Assurance Checklist
- [ ] Follows spacing system
- [ ] Uses correct color variables
- [ ] Responsive at all breakpoints
- [ ] Accessible keyboard navigation
- [ ] Consistent typography
- [ ] Proper hover/focus states
- [ ] Loading/error states implemented
- [ ] Cross-browser tested
- [ ] Performance optimized
- [ ] Documentation updated

---

*This document should be referenced when creating or modifying any template in the Baysoko Marketplace. Consistency across the platform is essential for user experience and brand identity.*
