export class Scene {
  constructor() {
    this.objects = [];
  }
  add(object) {
    this.objects.push(object);
  }
}

export class PerspectiveCamera {
  constructor() {
    this.position = { x: 0, y: 6, z: 8 };
  }
}

export class WebGLRenderer {
  constructor(options) {
    this.canvas = options.canvas;
    this.ctx = this.canvas.getContext("2d");
  }
  setSize(width, height) {
    this.canvas.width = width;
    this.canvas.height = height;
  }
  render(scene) {
    const ctx = this.ctx;
    const width = this.canvas.width;
    const height = this.canvas.height;
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "#dfe7ee";
    ctx.fillRect(0, 0, width, height);
    for (const object of scene.objects) {
      if (typeof object.draw === "function") {
        object.draw(ctx, width, height);
      }
    }
  }
}
