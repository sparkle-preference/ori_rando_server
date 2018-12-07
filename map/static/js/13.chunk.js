webpackJsonp([13],{

/***/ "./node_modules/css-loader/index.js?{\"importLoaders\":1}!./node_modules/postcss-loader/lib/index.js?{\"ident\":\"postcss\"}!./src/index.css":
/*!***************************************************************************************************************************!*\
  !*** ./node_modules/css-loader?{"importLoaders":1}!./node_modules/postcss-loader/lib?{"ident":"postcss"}!./src/index.css ***!
  \***************************************************************************************************************************/
/*! dynamic exports provided */
/*! all exports used */
/***/ (function(module, exports, __webpack_require__) {

exports = module.exports = __webpack_require__(/*! ../node_modules/css-loader/lib/css-base.js */ "./node_modules/css-loader/lib/css-base.js")(undefined);
// imports


// module
exports.push([module.i, "\nhtml, body {\n  height: 100%;\n  margin: 0;\n}\n\nbody, #root, #app {\n  height: 100%;\n}\n\n#app {\n  display: -ms-flexbox;\n  display: flex;\n  -ms-flex-direction: column;\n      flex-direction: column;\n}\n\nmain {\n  -ms-flex-positive: 1;\n      flex-grow: 1;\n  display: -ms-flexbox;\n  display: flex;\n  -ms-flex-direction: column;\n      flex-direction: column;\n}\n\n.stretch {\n  width: 100%;\n  height: 100%;\n  min-height: 600px;\n}\n\n.wrapper {\n  display: -ms-flexbox;\n  display: flex;\n  width: 100%;\n  height: 100%;\n}\n\n.board-container {\n  display: -ms-flexbox;\n  display: flex;\n  -ms-flex-direction: column;\n      flex-direction: column;\n  -ms-flex-positive: 1;\n      flex-grow: 1;\n}\n\n.leaflet-container {\n  height: 100%;\n  -ms-flex-positive: 1;\n      flex-grow: 1;\n  background: rgb(18, 18, 18);\n}\n\n.controls {\n  width: 450px;\n  height: 100%;\n  float: right;\n  overflow-x: hidden;\n  overflow-y: auto;\n  padding: 10px;\n\n  color: white;\n}\n\n#file-controls {\n  width: 100%;\n  display: -ms-flexbox;\n  display: flex;\n  -ms-flex-pack: justify;\n      justify-content: space-between;\n  margin-bottom: 16px;\n}\n\n#import-wrapper {\n  padding-left: 8px;\n  padding-right: 8px;\n}\n\n#import-seed-area{\n  margin-bottom: 16px;\n}\n\n#pickup-controls {\n  width: 100%;\n  margin-bottom: 16px;\n}\n\n#pickup-controls .label {\n  width: 90px;\n}\n\n#pickup-controls > .pickup-wrapper {\n  width: 100%;\n  height: 100%;\n  display: -ms-flexbox;\n  display: flex;\n  -ms-flex-align: center;\n      align-items: center;\n  margin-bottom: 4px;\n}\n\n#pickup-controls > .pickup-wrapper > div {\n  -ms-flex-positive: 1;\n      flex-grow: 1;\n}\n\n#fill-params {\n  width: 100%;\n}\n\n.fill-wrapper {\n  width: 100%;\n  height: 36px;\n  display: -ms-flexbox;\n  display: flex;\n  -ms-flex-align: center;\n      align-items: center;\n  -ms-flex-pack: justify;\n      justify-content: space-between;\n  margin-bottom: 4px;\n}\n\n.fill-wrapper > .react-numeric-input {\n  width: 80px;\n}\n\n#fill-params > .checkbox-label {\n  width: 100%;\n}\n\n#display-controls {\n  width: 100%;\n  margin-bottom: 16px;\n}\n\n#display-controls .label {\n  width: 90px;\n}\n\n#display-flags {\n  width: 100%;\n  margin-top: 4px;\n  margin-bottom: 4px;\n  display: -ms-flexbox;\n  display: flex;\n  -ms-flex-line-pack: center;\n      align-content: center;\n  -ms-flex-pack: justify;\n      justify-content: space-between;\n}\n\n#logic-controls {\n  width: 100%;\n  margin-bottom: 16px;\n}\n\n#logic-mode-wrapper {\n  width: 100%;\n  margin-bottom: 16px;\n}\n\n#logic-mode-wrapper .label {\n  width: 90px;\n}\n\n#manual-controls {\n  width: 100%;\n  padding-left: 8px;\n  padding-right: 8px;\n}\n\n.manual-wrapper {\n  width: 100%;\n  height: 100%;\n  margin-bottom: 4px;\n  display: -ms-flexbox;\n  display: flex;\n  -ms-flex-line-pack: center;\n      align-content: center;\n}\n\n.manual-wrapper .label {\n  width: 90px;\n}\n\n.manual-wrapper .react-numeric-input {\n  -ms-flex-positive: 1;\n      flex-grow: 1;\n}\n\n.manual-wrapper > div {\n  -ms-flex-positive: 1;\n      flex-grow: 1;\n}\n\n#logic-mode-controls {\n  width: 100%;\n}\n\n#logic-presets {\n  width: 100%;\n  display: -ms-flexbox;\n  display: flex;\n  -ms-flex-line-pack: center;\n      align-content: center;\n  margin-bottom: 4px;\n}\n\n#logic-presets > div {\n  -ms-flex-positive: 1;\n      flex-grow: 1;\n}\n\n#logic-options-wrapper {\n  width: 100%;\n  padding-left: 8px;\n  padding-right: 8px;\n}\n\n#logic-options {\n  width: 100%;\n  display: inline-grid;\n  grid-template-columns: auto auto auto;\n  grid-template-rows: auto auto auto auto auto auto;\n  -ms-flex-pack: justify;\n      justify-content: space-between;\n}\n\n.basic-coop-options {\n  width: 100%;\n  display: -ms-flexbox;\n  display: flex;\n  -ms-flex-line-pack: center;\n      align-content: center;\n  margin-bottom: 4px;\n}\n\n.basic-coop-options .label{\n  width: 90px;\n  margin-left: 10px;\n  margin-top: 5px;\n}\n.basic-coop-options .Select{\n  width: auto;\n}\n#coop-wrapper {\n  width: 100%;\n  padding-left: 8px;\n  padding-right: 8px;\n}\n\n.coop-select-wrapper {\n  width: 100%;\n  height: 36px;\n  margin-bottom: 4px;\n  display: -ms-flexbox;\n  display: flex;\n  -ms-flex-line-pack: center;\n      align-content: center;\n}\n\n.coop-select-wrapper .label {\n  width: 90px;\n}\n\n.coop-select-wrapper > div {\n  -ms-flex-positive: 1;\n      flex-grow: 1;\n}\n\n#flag-controls {\n  width: 100%;\n  display: -ms-flexbox;\n  display: flex;\n  -ms-flex-line-pack: center;\n      align-content: center;\n  margin-bottom: 16px;\n}\n\n#flag-controls .label{\n  width: 90px;\n}\n\n#search-wrapper {\n  width: 100%;\n  margin-bottom: 16px;\n}\n\n#map-controls {\n  width: 100px;\n  margin-top: 16px;\n  margin-bottom: 16px;\n}\n\n#player-controls {\n  width: 100%;\n  margin-bottom: 4px;\n}\n\n.player-wrapper {\n  width: 100%;\n  padding-left: 8px;\n  padding-right: 8px;\n}\n\n.player_name {\n  display: block;\n  width: 100%;\n}\n\n.player-options {\n  width: 100%;\n  display: grid;\n  grid-template-columns: auto auto auto;\n  grid-template-rows: auto auto;\n  grid-gap: 2px;\n  -ms-flex-pack: justify;\n      justify-content: space-between;\n}\n\n#pickup-wrapper {\n  width: 100%;\n  padding-left: 8px;\n  padding-right: 8px;\n  display: grid;\n  grid-template-columns: auto auto auto;\n  grid-template-rows: auto auto auto;\n  -ms-flex-pack: justify;\n      justify-content: space-between;\n}\n\n.radio-label {\n\tpadding-left: 4px;\n\tpadding-right: 4px;\n}\n.control-label {\n  width: 100%;\n}\n\n#map-controls {\n  width: 100%;\n  margin-bottom: 4px;\n}\n\n.react-confirm-alert-body > h1 {\n\tcolor: #666;\n\tfont-size: 28px;\n\tfont-weight: 700;\n}", ""]);

// exports


/***/ }),

/***/ "./src/index.css":
/*!***********************!*\
  !*** ./src/index.css ***!
  \***********************/
/*! dynamic exports provided */
/*! all exports used */
/***/ (function(module, exports, __webpack_require__) {

// style-loader: Adds some css to the DOM by adding a <style> tag

// load the styles
var content = __webpack_require__(/*! !../node_modules/css-loader??ref--1-oneOf-2-1!../node_modules/postcss-loader/lib??postcss!./index.css */ "./node_modules/css-loader/index.js?{\"importLoaders\":1}!./node_modules/postcss-loader/lib/index.js?{\"ident\":\"postcss\"}!./src/index.css");
if(typeof content === 'string') content = [[module.i, content, '']];
// Prepare cssTransformation
var transform;

var options = {"hmr":true}
options.transform = transform
// add the styles to the DOM
var update = __webpack_require__(/*! ../node_modules/style-loader/lib/addStyles.js */ "./node_modules/style-loader/lib/addStyles.js")(content, options);
if(content.locals) module.exports = content.locals;
// Hot Module Replacement
if(true) {
	// When the styles change, update the <style> tags
	if(!content.locals) {
		module.hot.accept(/*! !../node_modules/css-loader??ref--1-oneOf-2-1!../node_modules/postcss-loader/lib??postcss!./index.css */ "./node_modules/css-loader/index.js?{\"importLoaders\":1}!./node_modules/postcss-loader/lib/index.js?{\"ident\":\"postcss\"}!./src/index.css", function() {
			var newContent = __webpack_require__(/*! !../node_modules/css-loader??ref--1-oneOf-2-1!../node_modules/postcss-loader/lib??postcss!./index.css */ "./node_modules/css-loader/index.js?{\"importLoaders\":1}!./node_modules/postcss-loader/lib/index.js?{\"ident\":\"postcss\"}!./src/index.css");
			if(typeof newContent === 'string') newContent = [[module.i, newContent, '']];
			update(newContent);
		});
	}
	// When the module is disposed, remove the <style> tags
	module.hot.dispose(function() { update(); });
}

/***/ })

});
//# sourceMappingURL=13.chunk.js.map