const { merge } = require('webpack-merge');
const commonConfig = require('./common.config');
const dev_server_port = process.env.DEV_SERVER_PORT || 3001;
const proxy_address = process.env.PROXY_ADDRESS || 'http://localhost:8001';
module.exports = merge(commonConfig, {
  mode: 'development',
  devtool: 'inline-source-map',
  devServer: {
    port: dev_server_port,
    proxy: {
      '/': proxy_address
    },
    // We need hot=false (Disable HMR) to set liveReload=true
    hot: false,
    liveReload: true,
  },
});
