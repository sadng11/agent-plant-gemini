import { createRouter, createWebHistory } from 'vue-router';
import GardenDashboard from '../components/garden/GardenDashboard.vue';
import ChatWindow from '../components/chat/ChatWindow.vue';

const routes = [
  {
    path: '/',
    redirect: '/garden',
  },
  {
    path: '/garden',
    name: 'garden',
    component: GardenDashboard,
    meta: {
      title: 'باغچه من | فیتو',
    },
  },
  {
    path: '/chat',
    name: 'chat',
    component: ChatWindow,
    meta: {
      title: 'کلینیک و چت تشخیصی | فیتو',
    },
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/garden',
  },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to, _from, next) => {
  if (to.meta.title) {
    document.title = to.meta.title as string;
  }
  next();
});

export default router;
