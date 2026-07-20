// 웹푸시 서비스워커. 탭/브라우저가 닫혀있어도 서버가 보낸 push 메시지를 받아 OS 알림으로
// 띄우는 역할을 한다 - 지금 있던 Notification API(포그라운드 폴링, AlarmPage.tsx의
// checkAndFire)와 달리, 진짜 백그라운드 알림은 이 서비스워커를 거쳐야만 가능하다.

self.addEventListener("push", (event) => {
  let payload = { title: "복약 알림", body: "복약 시간이에요!" };
  try {
    if (event.data) {
      payload = event.data.json();
    }
  } catch {
    // 서버가 JSON이 아닌 형태로 보냈으면 기본 문구로 대체 - 알림 자체는 뜨게 한다.
  }

  event.waitUntil(self.registration.showNotification(payload.title, { body: payload.body }));
});

// 알림을 클릭하면 이미 열려있는 탭이 있으면 그걸 포커스하고, 없으면 새로 연다.
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if ("focus" in client) return client.focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow("/alarms");
      return undefined;
    }),
  );
});
