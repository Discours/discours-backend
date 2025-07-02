declare module "*.svg" {
	const content: string;
	export default content;
}

declare module "*.svg?component" {
	import type { Component } from "solid-js";
	const component: Component;
	export default component;
}

declare module "*.svg?url" {
	const url: string;
	export default url;
}
