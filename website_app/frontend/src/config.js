// API configuration
const API_CONFIG = {
  baseURL: "https://ota-website-app.azurewebsites.net/api" || "http://localhost:5000/api" ,
  endpoints: {
    carTypes: "/car-types",
    ecus: "/ecus",
    versions: "/versions",
    requests: "/requests",
  },
};

export default API_CONFIG;
