FROM nginx:alpine
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY index.html app.js /usr/share/nginx/html/
COPY assets/ /usr/share/nginx/html/assets/

# API_UPSTREAM is resolved by nginx's envsubst-on-start:
#   docker-compose: dqc-api:8000
#   ECS Fargate:    localhost:8000
ENV API_UPSTREAM=dqc-api:8000

EXPOSE 80
