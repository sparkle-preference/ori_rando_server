const { createProxyMiddleware } = require("http-proxy-middleware");
const injector = require('connect-injector');
const Mustache = require('mustache');

const templates = {
    "/":{
        "app": "MainPage",
        "title": "DEV SERVER - Ori Randomizer",
        "dark":"false",
    },
}

//some doubled paths
templates["/quickstart"] = templates["/"];

const pathInTemplates = function (path) {
    path = removeBits(path);
    for(const template in templates){
        if(path === template){
            return true;
        }
    }
    return false;
}

const removeBits = (path) => path
    .split(/[?#]/)[0]
    .replace(/index.html$/, "");

module.exports = function (app) {
    app.use(createProxyMiddleware({
        target: "http://localhost:8080/",
        pathFilter: (path, req) =>{
            path = removeBits(path);
            return !(path in templates || path.match(/\.\w+$/));
        }
    }));
    app.use(injector(function(req, res) {
            console.log(`${req.url}, ${removeBits(req.url)}, ${pathInTemplates(removeBits(req.url))}`);
            return pathInTemplates(removeBits(req.url));
        },
        function(data, req, res, callback) {
            callback(null, Mustache.render(data.toString(), templates[removeBits(req.url)]));
        }
    ));
    

};
