// api.js
const API_CONFIG = {
  baseURL: process.env.REACT_APP_API_URL.endsWith('/')
    ? process.env.REACT_APP_API_URL
    : process.env.REACT_APP_API_URL + '/',
  endpoints: {
    carTypes: "car-types",
    ecus:     "ecus",
    versions: "versions",
    requests:"requests",
  },
};
