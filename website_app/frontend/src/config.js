// src/apiConfig.js
const API_BASE =
  process.env.REACT_APP_API_URL ||
  "https://ota-website-app.azurewebsites.net/api";

const ENDPOINTS = {
  carTypes: "/car-types",
  ecus:     "/ecus",
  versions: "/versions",
  requests: "/requests",
};

export default { API_BASE, ENDPOINTS };
