# MERCON Assets

## Icons

### Icon Library: lucide-react-native

MERCON uses `lucide-react-native` for all icons. No other icon library is permitted. Emoji icons used in the current screen source files are development placeholders and must be replaced with lucide icons in production.

**Install:**
```bash
npm install lucide-react-native react-native-svg
```

**Usage:**
```typescript
import { Home, Truck, User, Plus, Search, Bell, Settings, ChevronRight } from 'lucide-react-native';

<Truck size={20} color={Colors.primary} />
```

### Icon Size Scale

| Context | Size | Color (default) |
|---------|------|-----------------|
| Navigation tabs (Driver) | 20px | `Colors.primary` (active), `rgba(255,255,255,0.45)` (inactive) |
| Navigation tabs (Operator) | 18px | Same as above |
| FAB | 22px (`Plus` icon) | `Colors.primary` |
| Input prefix/suffix | 16px | `Colors.gray400` |
| Button prefix/suffix | 16px (sm/md), 18px (lg) | Inherits from button variant |
| Card row indicator | 16px | `Colors.gray400` |
| Section header | 20px | `Colors.gray500` |
| Toast / notification | 18px | Semantic (success/danger/warning) |
| Tab bar (web) | 18px | `Colors.gray500` (inactive), `Colors.primary` (active) |

### Icon Mapping by Feature

| Feature / Element | Lucide Icon | Usage |
|------------------|------------|-------|
| Home / Dashboard | `Home` | Driver tab, Operator tab, Web sidebar |
| Trips | `Truck` | Driver tab, Operator tab, Web sidebar |
| Profile | `User` | Driver tab |
| Drivers | `Users` | Operator tab, Web sidebar |
| More | `MoreHorizontal` | Operator tab |
| Add / FAB | `Plus` | Operator FAB, Add buttons |
| Search | `Search` | SearchInput component |
| Notifications | `Bell` | Notification bell, Profile section |
| Settings | `Settings` | Settings sections |
| Back | `ArrowLeft` | Back navigation button |
| Navigation | `Navigation` or `MapPin` | Start navigation action |
| Location pin | `MapPin` | Route origin/destination |
| Phone | `Phone` | Call driver action |
| Message | `MessageCircle` | Message driver action |
| Camera | `Camera` | POD upload, document capture |
| Upload | `Upload` | Document upload |
| Check / confirmed | `CheckCircle` | Success states, delivery confirmation |
| Warning | `AlertTriangle` | Delayed status, expiring documents |
| Error | `XCircle` | Cancelled, error states |
| Clock | `Clock` | Pending status, ETA |
| Calendar | `Calendar` | Date inputs, trip scheduling |
| Invoice | `FileText` | Invoice list, invoice details |
| Vehicle | `Truck` | Vehicle list (or `Car` for lighter vehicles) |
| Documents | `FolderOpen` | Document vault |
| Emergency | `AlertOctagon` | Emergency screen |
| Earnings | `DollarSign` | Earnings screen |
| Rate card | `Tag` | Rate card list |
| Reports | `BarChart2` | Reports section |
| Customers | `Building2` | Customer list, web sidebar |
| Filter | `Filter` | Filter action button |
| Sort | `ArrowUpDown` | Sort action button |
| Download | `Download` | Export/download PDF |
| Share | `Share2` | Share trip, share invoice |
| Edit | `Pencil` | Edit action |
| Delete | `Trash2` | Delete action (danger) |
| Logout | `LogOut` | Logout button |
| Refresh | `RefreshCw` | Retry / pull-to-refresh |
| Star / rating | `Star` | Driver rating display |
| Weight | `Scale` | Cargo weight |
| Speed | `Gauge` | Vehicle speed |
| Fuel | `Fuel` | Vehicle fuel type |
| Distance | `Route` | Distance display |

---

## Logo

### MERCON Logotype

- **Format:** SVG (preferred), PNG fallback
- **Composition:** MERCON wordmark with an orange truck icon mark to the left
- **Versions:**
  - Full color (dark wordmark + orange truck): use on white/light backgrounds
  - Reversed (white wordmark + orange truck): use on dark backgrounds (`#1C1C2E`)
  - Icon-only (orange truck mark): use for app icon, favicon, avatar fallback
  - Monochrome (all-white): use on photographic backgrounds

### Usage by context

| Context | Logo Version |
|---------|-------------|
| Splash screen | Reversed (white wordmark) on dark background |
| Login screen header | Full color on light background |
| Web dashboard sidebar | Reversed (white) on dark sidebar |
| App icon | Icon-only (orange truck on white or dark background) |
| Email templates | Full color on white |
| Push notification | Icon-only (system icon slot) |

### Size guidelines

| Context | Width | Height |
|---------|-------|--------|
| Mobile header | 120px | auto |
| Splash screen center | 180px | auto |
| Web sidebar | 140px | auto |
| App icon (iOS) | 1024×1024px | exported at 1×, 2×, 3× |
| Favicon | 32×32px | .ico + SVG |

---

## Illustrations

MERCON uses minimal line illustrations for empty states. These are simple SVG graphics, not photographs.

### Empty state illustrations

| Screen | Illustration | Description |
|--------|-------------|-------------|
| No active trips | Truck parked on road | Simple line art, orange truck, gray road |
| No notifications | Bell with zzz | Bell icon with sleep indicator |
| No drivers | Person silhouette | Single user outline with plus |
| Documents vault empty | Folder with document | Open folder, document inside |
| Earnings empty | Chart bars | Simple bar chart outline |
| Search no results | Magnifying glass | Magnifier with X mark |
| Network error | Cloud with X | Disconnected cloud |
| Generic error | Triangle warning | Outlined warning triangle |

### Illustration style guidelines

- Monochrome with MERCON Orange as the single accent color
- Line weight: 2px strokes
- Colors: `Colors.gray200` for base elements, `Colors.primary` for accent elements
- Size: displayed at approximately 120×120pt in most empty states
- Format: SVG (inline or referenced)

---

## Background and Gradients

### Screen backgrounds

| Surface | Color | Token |
|---------|-------|-------|
| Screen background | `#F5F5F7` | `Colors.gray100` |
| Card surface | `#FFFFFF` | `Colors.white` |
| Dark card | `#1C1C2E` | `Colors.darkCard` |
| Navigation pill | `#1C1C2E` | `Colors.navBg` |

### Gradients

MERCON uses minimal gradients. The following are the only permitted gradients:

1. **Primary gradient** (for future hero sections, not current use):
   - From: `#E8450F` (MERCON Orange)
   - To: `#C7380A` (primaryDark)
   - Direction: 135deg (bottom-right)

2. **Dark surface gradient** (for map screen overlay):
   - From: `rgba(28, 28, 46, 0)` (transparent)
   - To: `rgba(28, 28, 46, 0.9)` (nearly opaque dark)
   - Direction: 0deg (bottom)
   - Use: on map screen bottom sheet backdrop

3. **Skeleton shimmer gradient** (for loading states):
   - Colors: `#EBEBED → #F5F5F7 → #EBEBED`
   - Direction: left to right, animated

---

## Map Tiles

The LiveNavigation screen uses map tiles. Recommended providers:

- **Mapbox** — customizable dark map style recommended for the navigation screen
- **Google Maps** — fallback via `react-native-maps`

### Map style for MERCON

- Dark map style (Night mode) for active navigation
- Standard map style for trip detail previews (thumbnail)
- Primary route line color: `Colors.primary` (`#E8450F`)
- Route polyline width: 4pt
- Origin marker: green dot
- Destination marker: orange MERCON pin

---

## Asset Export Specifications

### For React Native

| Asset Type | Format | Export Scale |
|-----------|--------|-------------|
| App icon | PNG | 1×, 2×, 3× |
| Splash screen logo | PNG | 1×, 2×, 3× |
| Illustrations | SVG (react-native-svg) | 1 file, renders at any size |
| Map pin icon | PNG | 1×, 2×, 3× |
| Notification icon (Android) | PNG | mdpi, hdpi, xhdpi, xxhdpi, xxxhdpi |

### For Web

| Asset Type | Format | Size |
|-----------|--------|------|
| Favicon | ICO + SVG | 16, 32, 48px |
| Open Graph image | PNG | 1200×630px |
| Sidebar logo | SVG | vector |
| Illustrations | SVG | vector |

---

## Naming Conventions

All asset files follow this naming convention:

```
{product}-{name}-{variant}-{size}.{ext}

Examples:
mercon-logo-full-color.svg
mercon-logo-reversed.svg
mercon-logo-icon-only.svg
mercon-icon-app-1024.png
mercon-illustration-empty-trips.svg
mercon-illustration-empty-notifications.svg
mercon-map-pin-origin.png
mercon-map-pin-destination.png
```

---

## Dependencies

| Dependency | Version | Purpose |
|-----------|---------|---------|
| `lucide-react-native` | latest | All icons |
| `react-native-svg` | latest | SVG rendering (required by lucide) |
| `react-native-maps` | latest | Map views |
| `expo-font` | latest | Font loading |
| `expo-image-picker` | latest | Camera/gallery for POD upload |
| `expo-file-system` | latest | Local file storage for cached images |
