// src/config.js
export default {
  baseURL: process.env.REACT_APP_API_URL?.replace(/\/$/, "") || "https://ota-website-app.azurewebsites.net/api",
  endpoints: {
    carTypes:   "/car-types",
    ecus:       "/ecus",
    versions:   "/versions",
    requests:   "/requests",
  },
};