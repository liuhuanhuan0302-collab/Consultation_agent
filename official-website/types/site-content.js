/**
 * @typedef {Object} LinkItem
 * @property {string} label
 * @property {string} href
 */

/**
 * @typedef {Object} Metric
 * @property {string} key
 * @property {string} label
 * @property {number=} value
 * @property {string=} displayValue
 * @property {string=} suffix
 */

/**
 * @typedef {Object} ContentCard
 * @property {string} id
 * @property {string} title
 * @property {string=} label
 * @property {string=} lead
 * @property {string} description
 */

/**
 * @typedef {Object} BusinessModule
 * @property {string} id
 * @property {string} name
 * @property {string} core
 * @property {string} value
 * @property {string} method
 */

/**
 * @typedef {Object} TransformationStage
 * @property {string} id
 * @property {string} name
 * @property {string} description
 */

/**
 * @typedef {Object} SiteContent
 * @property {{version: string, updatedAt: string, sources: string[]}} meta
 * @property {{name: string, positioning: string, profile: string, mission: string, vision: string, values: string[]}} company
 * @property {{eyebrow: string, title: string, description: string, actions: LinkItem[]}} hero
 * @property {{scenarioCount: number, agentAvailability: string}} facts
 * @property {string[]} serviceChain
 * @property {Metric[]} metrics
 * @property {ContentCard[]} painPoints
 * @property {{title: string, description: string, dimensions: string[], outputs: string[]}} diagnosis
 * @property {ContentCard[]} solutions
 * @property {TransformationStage[]} transformationStages
 * @property {BusinessModule[]} businessModules
 * @property {{principles: Array<{name: string, description: string}>}} methodology
 * @property {{phone: string|null, email: string|null, bookingUrl: string|null}} contact
 */

export {};
