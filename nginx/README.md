# Nginx Blue-Green Traffic Switching Configuration

This directory contains the upstream configuration files for blue-green deployment traffic switching.

## Files

- **upstream-blue.conf**: Defines the upstream to point to the blue container (`kr-app-prod-blue:8000`)
- **upstream-green.conf**: Defines the upstream to point to the green container (`kr-app-prod-green:8000`)
- **upstream-active.conf**: Symlink that points to either `upstream-blue.conf` or `upstream-green.conf`

## How It Works

The `nginx.prod.conf` includes `/etc/nginx/conf.d/upstream-active.conf`, which is a symlink managed by the deployment script. When traffic is switched during deployment:

1. The deployment script determines the target color (blue or green)
2. Updates the symlink: `ln -sf /etc/nginx/conf.d/upstream-{color}.conf /etc/nginx/conf.d/upstream-active.conf`
3. Verifies the symlink points to the correct file
4. Reloads nginx: `nginx -s reload`

## Initial Setup

Before the first deployment, create the initial symlink to point to blue:

```bash
# On the host (if nginx directory is mounted)
cd nginx
ln -sf upstream-blue.conf upstream-active.conf

# Or inside the nginx container
docker exec kr-nginx-prod ln -sf /etc/nginx/conf.d/upstream-blue.conf /etc/nginx/conf.d/upstream-active.conf
docker exec kr-nginx-prod nginx -s reload
```

## Verification

To verify which upstream is currently active:

```bash
# Check the symlink
docker exec kr-nginx-prod readlink /etc/nginx/conf.d/upstream-active.conf

# Test the health endpoint
curl http://<prod-host>/health
```

## Troubleshooting

If nginx fails to start or reload:

1. Check nginx configuration syntax:

   ```bash
   docker exec kr-nginx-prod nginx -t
   ```

2. Verify the symlink exists and points to a valid file:

   ```bash
   docker exec kr-nginx-prod ls -la /etc/nginx/conf.d/
   ```

3. Check nginx logs:

   ```bash
   docker logs kr-nginx-prod
   ```

4. Ensure both app containers are running:

   ```bash
   docker ps | grep kr-app-prod
   ```
