export default async function CegResztPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="flex flex-col gap-2">
      <h1 className="text-2xl font-semibold">Cég részletei</h1>
      <p className="text-sm text-muted-foreground">
        A részletnézet az F4 fázisban készül el. (id: {id})
      </p>
    </div>
  );
}
