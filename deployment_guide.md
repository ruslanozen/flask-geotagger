# Image Processor Web Application - Deployment Guide

## Overview
This document provides instructions for deploying the Image Processor Web Application on a cPanel server. The application is a Flask-based web version of your desktop image processing tool, with all the same functionality accessible through a web browser.

## Prerequisites
- cPanel access with Python support
- Ability to install Python packages via pip
- ExifTool installed on the server (or ability to install it)

## Deployment Steps

### 1. Upload the Application
1. Log in to your cPanel account
2. Navigate to the File Manager
3. Go to the directory where you want to deploy the application (e.g., `public_html/image_processor`)
4. Upload the `image_processor_web_deploy.zip` file
5. Extract the zip file in that location

### 2. Set Up Python Environment
1. In cPanel, navigate to "Setup Python App"
2. Create a new Python application with the following settings:
   - Python version: 3.8 or higher
   - Application root: The directory where you extracted the files (e.g., `/public_html/image_processor`)
   - Application URL: Your preferred URL path (e.g., `/image_processor`)
   - Application startup file: `src/main.py`
   - Application Entry point: `app`

3. In the "Environment variables" section, add:
   ```
   FLASK_ENV=production
   ```

### 3. Install Dependencies
1. Connect to your server via SSH
2. Navigate to your application directory
3. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Install ExifTool if not already available:
   ```bash
   # For CentOS/RHEL-based systems
   sudo yum install perl-Image-ExifTool
   
   # For Debian/Ubuntu-based systems
   sudo apt-get install exiftool
   ```

### 4. Configure the Application
1. Ensure the application has write permissions for temporary file storage:
   ```bash
   chmod -R 755 /path/to/application
   ```

2. If needed, modify `src/main.py` to adjust paths or settings for your server environment

### 5. Start the Application
1. In cPanel, restart your Python application
2. The application should now be accessible at your configured URL

## Troubleshooting

### Common Issues:
1. **500 Internal Server Error**:
   - Check the error logs in cPanel
   - Ensure all dependencies are installed correctly
   - Verify file permissions

2. **ExifTool Not Found**:
   - Confirm ExifTool is installed on the server
   - Update the path to ExifTool in the application if necessary

3. **File Upload Issues**:
   - Check PHP upload limits in cPanel
   - Ensure temporary directories have proper permissions

## Maintenance

### Updating the Application:
1. Upload new files to the server
2. Replace the existing files
3. Restart the Python application in cPanel

### Backing Up:
1. Regularly back up the `static/data` directory which contains your presets
2. Consider setting up automatic backups in cPanel

## Security Considerations
1. The application does not include authentication by default
2. Consider adding password protection via .htaccess or implementing user authentication
3. Regularly update dependencies to patch security vulnerabilities

## Support
If you encounter any issues during deployment or use, please refer to the validation report for details on the application's functionality and requirements.

---

This deployment guide assumes a standard cPanel environment. Your specific hosting provider may have slightly different procedures for Python application deployment.
