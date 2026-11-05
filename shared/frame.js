/* Each animation implements render(step); the parent owns all navigation. */
window.registerAnimation = ({steps, render}) => {
  if (!Number.isInteger(steps) || steps < 0) throw Error('steps must be a nonnegative integer');
  window.animation = {steps, step: 0, setStep(n) {
    this.step = Math.max(0, Math.min(steps, n));
    render(this.step);
    document.documentElement.dataset.step = this.step;
  }};
  window.animation.setStep(0);
};
