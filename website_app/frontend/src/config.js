// api.js
const API_CONFIG = {
  baseURL: process.env.REACT_APP_API_URL,   // comes from the build-time ENV
  endpoints: {
    carTypes: "/car-types",
    ecus:     "/ecus",
    versions: "/versions",
    requests: "/requests",
  },
};

export default API_CONFIG;
