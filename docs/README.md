![PaleoPAL Logo](https://github.com/LinkedEarth/Logos/blob/master/PaleoPAL/PaleoPal_rectangular_light.png?raw=true)

[![DOI](https://zenodo.org/badge/990262252.svg)](https://doi.org/10.5281/zenodo.19341100)

# PaleoPAL: An AI Assistant for Paleoclimatology

This directory contains the GitHub Pages website for PaleoPal.

## Setup Instructions

### 1. Enable GitHub Pages

1. Go to your repository settings on GitHub
2. Navigate to "Pages" in the left sidebar
3. Under "Source", select:
   - **Source**: `Deploy from a branch`
   - **Branch**: `main` (or your default branch)
   - **Folder**: `/docs`
4. Click "Save"

### 2. Automatic Deployment

The website will automatically deploy when you push changes to files in the `docs/` directory, thanks to the GitHub Actions workflow (`.github/workflows/pages.yml`).

### 3. Manual Deployment

If you need to manually trigger a deployment:
1. Go to the "Actions" tab in your repository
2. Select "Deploy GitHub Pages" workflow
3. Click "Run workflow"

### 4. Access Your Site

After deployment, your site will be available at:
```
https://yourusername.github.io/paleopal/
```

## Customization

### Adding Demo Videos

To add demo videos, edit `index.html` and replace the video placeholders in the Demos section with embedded video iframes:

```html
<div class="demo-item">
    <h3>Your Demo Title</h3>
    <div class="video-container">
        <iframe 
            src="https://www.youtube.com/embed/YOUR_VIDEO_ID" 
            frameborder="0" 
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
            allowfullscreen>
        </iframe>
    </div>
</div>
```

### Updating Content

- **Philosophy**: Edit the `#philosophy` section in `index.html`
- **Installation**: Update the `#installation` section with latest instructions
- **FAQs**: Add or modify FAQ items in the `#faqs` section
- **Styling**: Modify `styles.css` to change colors, fonts, or layout

### Adding Images

Place images in the `docs/` directory and reference them in HTML:
```html
<img src="your-image.png" alt="Description">
```

## File Structure

```
docs/
├── index.html      # Main website page
├── styles.css      # Stylesheet
└── README.md       # This file
```

## Notes

- The website uses a clean, academic design inspired by research documentation sites
- All links in the footer should be updated with your actual GitHub repository URL
- The site is fully responsive and works on mobile devices

