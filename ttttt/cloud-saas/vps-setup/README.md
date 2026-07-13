# Kamal Express SaaS - VPS Setup

This folder contains all the files needed to deploy the application on a production VPS (like Hetzner, DigitalOcean) using Docker and a Cloudflare Tunnel.

**Zero-Config Magic:** I have pre-generated secure VAPID keys, a secure `SECRET_KEY`, and secure internal database credentials directly into the `docker-compose.prod.yml`. This means you do **NOT** need to configure any environment variables yourself! 

## Option 1: Portainer Stacks (Recommended for GUI Users)

If you have Portainer installed on your VPS, you can deploy this entire application with one click.

1. In Portainer, go to **Stacks** -> **Add Stack**.
2. Select **Repository** (Git) and paste your GitHub repository URL.
3. For the **Compose path**, enter: `ttttt/cloud-saas/vps-setup/docker-compose.prod.yml`
4. In the **Environment variables** section, select "Load variables from .env file" and paste the contents of `.env.prod`.
5. Click **Deploy the Stack**. 
5. Portainer will build the Docker image and start the containers. Point your Cloudflare Tunnel to `http://localhost:8743`.

---

## Option 2: Command Line (Deploy Script)

If you prefer SSH and terminal access, you can deploy via the command line.

1. SSH into your VPS and clone the repository.
2. Navigate to the `vps-setup` directory.
3. Run the deployment script:
   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```
4. The application will build and bind to port `8743`. Point your Cloudflare Tunnel to `http://localhost:8743`.

> To update the app in the future, simply re-run `./deploy.sh`. It will automatically run `git pull` and rebuild the containers with zero downtime.
