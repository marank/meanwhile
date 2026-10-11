// jsdom doesn't lay out pages, so it has no scrolling; components may still ask for it.
Element.prototype.scrollIntoView ??= function () {}
